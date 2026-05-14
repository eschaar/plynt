"""Salesforce SOQL query service.

Provides sync and async services for the Salesforce Platform REST
``/query`` and ``/queryAll`` endpoints, including automatic pagination
helpers.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

from plynth.connectors.salesforce.constants import (
    resolve_async_api_version,
    resolve_sync_api_version,
)
from plynth.connectors.salesforce.helpers import build_select_soql
from plynth.connectors.salesforce.models import SalesforceQueryResponse
from plynth.connectors.salesforce.renderer import SalesforceRenderer
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import Renderer
from plynth.http.service import APIService, AsyncAPIService

__all__ = [
    "AsyncSalesforceObjectQueryService",
    "AsyncSalesforceQueryService",
    "SalesforceObjectQueryService",
    "SalesforceQueryService",
]

_SOQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _validate_timestamp_field(field_name: str) -> None:
    """Validate a timestamp field token used in incremental query helpers."""
    if not _SOQL_IDENTIFIER_RE.match(field_name):
        raise ValueError(f"Invalid timestamp field: {field_name!r}")


def _to_soql_utc_timestamp(since: datetime) -> str:
    """Convert a timezone-aware datetime to a SOQL UTC timestamp literal."""
    if since.tzinfo is None:
        raise ValueError("since must be timezone-aware")
    normalized = since.astimezone(UTC)
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


class SalesforceQueryService(APIService):
    """Service for Salesforce SOQL query endpoints.

    Provides ``query()``, ``query_more()``, ``query_all_iter()``, and
    ``query_all()`` — covering manual single-page, manual pagination, lazy
    generator, and eager full-result variants for both standard and
    include-deleted queries.

    Example::

        query_svc = facade.query()
        result = query_svc.query("SELECT Id, Name FROM Account LIMIT 10")
        for record in result.records:
            print(record["Name"])

        # Automatic pagination:
        for page in query_svc.query_all_iter("SELECT Id FROM Lead"):
            process(page.records)

        # Eager full result:
        all_records = query_svc.query_all("SELECT Id FROM Lead")

    """

    def __init__(
        self,
        client: APIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize SalesforceQueryService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = resolve_sync_api_version(client, api_version)

    def _query_path(self, *, include_deleted: bool = False) -> str:
        """Return the Salesforce query endpoint path."""
        endpoint = "queryAll" if include_deleted else "query"
        return f"/services/data/v{self._api_version}/{endpoint}"

    def query(
        self,
        soql: str,
        *,
        include_deleted: bool = False,
    ) -> SalesforceQueryResponse:
        """Execute a SOQL query and return the first page of results.

        When ``result.done`` is ``False``, more pages are available.
        Use ``query_more(result.next_records_url)`` to fetch the next page,
        or use ``query_all_iter()`` / ``query_all()`` to paginate
        automatically.

        Args:
            soql: A SOQL string, e.g.
                ``"SELECT Id, Name FROM Account WHERE IsDeleted = false"``.
            include_deleted: When ``True``, use Salesforce ``/queryAll`` so
                soft-deleted records are eligible to be returned.

        Returns:
            A ``SalesforceQueryResponse`` with the first page of records.

        """
        resp = self._client.get(
            self._query_path(include_deleted=include_deleted),
            params={"q": soql},
        )
        return SalesforceQueryResponse.model_validate_json(resp.content)

    def query_more(self, next_records_url: str) -> SalesforceQueryResponse:
        """Fetch the next page of a paginated SOQL result.

        Args:
            next_records_url: The ``nextRecordsUrl`` value from a previous
                ``SalesforceQueryResponse`` (e.g.
                ``"/services/data/v59.0/query/01g...XXXX-2000"``).

        Returns:
            A ``SalesforceQueryResponse`` with the next batch of records.

        """
        resp = self._client.get(next_records_url)
        return SalesforceQueryResponse.model_validate_json(resp.content)

    def query_more_from_id(
        self,
        next_records_id: str,
        *,
        include_deleted: bool = False,
    ) -> SalesforceQueryResponse:
        """Fetch the next page using only the Salesforce next-record cursor ID.

        Args:
            next_records_id: Cursor ID from a ``nextRecordsUrl`` value,
                e.g. ``"01g...XXXX-2000"``.
            include_deleted: When ``True``, use ``/queryAll/`` for cursor
                continuation. Keep this aligned with the originating query.

        Returns:
            A ``SalesforceQueryResponse`` with the next batch of records.

        """
        if not next_records_id or "/" in next_records_id:
            raise ValueError(
                "next_records_id must be a non-empty cursor token without '/'."
            )
        endpoint = "queryAll" if include_deleted else "query"
        next_records_url = (
            f"/services/data/v{self._api_version}/{endpoint}/{next_records_id}"
        )
        return self.query_more(next_records_url)

    def query_all_iter(
        self,
        soql: str,
        *,
        include_deleted: bool = False,
    ) -> Iterator[SalesforceQueryResponse]:
        """Lazily iterate over all pages of a SOQL query result.

        Yields one ``SalesforceQueryResponse`` per page.  Fetches the next
        page only when the iterator is advanced, so callers can stop early
        without unnecessary network calls.

        Args:
            include_deleted: When ``True``, start pagination through the
                ``/queryAll`` endpoint.

        Yields:
            ``SalesforceQueryResponse`` for each page until ``done`` is
            ``True``.

        Example::

            for page in query_svc.query_all_iter("SELECT Id FROM Lead"):
                for record in page.records:
                    process(record)

        """
        page = self.query(soql, include_deleted=include_deleted)
        yield page
        while not page.done and page.next_records_url:
            page = self.query_more(page.next_records_url)
            yield page

    def query_all(
        self,
        soql: str,
        *,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """Eagerly fetch all records across all pages of a SOQL query.

        Drives ``query_all_iter()`` to completion and returns every record
        in a single flat list.  Use this when you need all results at once
        and the total record count is manageable in memory.

        Args:
            include_deleted: When ``True``, fetch from ``/queryAll`` so
                soft-deleted records are included.

        Returns:
            A flat list of record dicts from all pages.

        Example::

            accounts = query_svc.query_all(
                "SELECT Id, Name FROM Account WHERE Type = 'Customer'"
            )

        """
        return [
            record
            for page in self.query_all_iter(
                soql,
                include_deleted=include_deleted,
            )
            for record in page.records
        ]


class AsyncSalesforceQueryService(AsyncAPIService):
    """Async service for Salesforce SOQL query endpoints.

    Async counterpart of ``SalesforceQueryService``.  Provides
    ``query()``, ``query_more()``, ``query_all_iter()``, and
    ``query_all()`` for both standard and include-deleted queries.

    ``query_all_iter()`` returns an ``AsyncIterator`` so callers can use
    ``async for`` without loading all records into memory.

    Example::

        query_svc = facade.query()
        result = await query_svc.query("SELECT Id, Name FROM Account LIMIT 10")

        async for page in query_svc.query_all_iter("SELECT Id FROM Lead"):
            for record in page.records:
                process(record)

    """

    def __init__(
        self,
        client: AsyncAPIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncSalesforceQueryService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = api_version
        self._version_lock = asyncio.Lock()

    async def _ensure_api_version(self) -> str:
        """Resolve and cache the API version once per service instance."""
        if self._api_version is None:
            async with self._version_lock:
                if self._api_version is None:
                    self._api_version = await resolve_async_api_version(
                        self._client,
                        self._api_version,
                    )
        return self._api_version

    async def _query_path(self, *, include_deleted: bool = False) -> str:
        """Return the Salesforce query endpoint path."""
        api_version = await self._ensure_api_version()
        endpoint = "queryAll" if include_deleted else "query"
        return f"/services/data/v{api_version}/{endpoint}"

    async def query(
        self,
        soql: str,
        *,
        include_deleted: bool = False,
    ) -> SalesforceQueryResponse:
        """Execute a SOQL query and return the first page of results.

        Args:
            include_deleted: When ``True``, use Salesforce ``/queryAll`` so
                soft-deleted records are eligible to be returned.

        Returns:
            A ``SalesforceQueryResponse`` with the first page of records.

        """
        query_path = await self._query_path(include_deleted=include_deleted)
        resp = await self._client.get(
            query_path,
            params={"q": soql},
        )
        return SalesforceQueryResponse.model_validate_json(resp.content)

    async def query_more(self, next_records_url: str) -> SalesforceQueryResponse:
        """Fetch the next page of a paginated SOQL result.

        Args:
            next_records_url: The ``nextRecordsUrl`` from a previous
                ``SalesforceQueryResponse``.

        Returns:
            A ``SalesforceQueryResponse`` with the next batch of records.

        """
        resp = await self._client.get(next_records_url)
        return SalesforceQueryResponse.model_validate_json(resp.content)

    async def query_more_from_id(
        self,
        next_records_id: str,
        *,
        include_deleted: bool = False,
    ) -> SalesforceQueryResponse:
        """Fetch the next page using only the Salesforce next-record cursor ID.

        Args:
            next_records_id: Cursor ID from a ``nextRecordsUrl`` value.
            include_deleted: When ``True``, use ``/queryAll/`` for cursor
                continuation. Keep this aligned with the originating query.

        Returns:
            A ``SalesforceQueryResponse`` with the next batch of records.

        """
        if not next_records_id or "/" in next_records_id:
            raise ValueError(
                "next_records_id must be a non-empty cursor token without '/'."
            )
        api_version = await self._ensure_api_version()
        endpoint = "queryAll" if include_deleted else "query"
        next_records_url = f"/services/data/v{api_version}/{endpoint}/{next_records_id}"
        return await self.query_more(next_records_url)

    async def query_all_iter(
        self,
        soql: str,
        *,
        include_deleted: bool = False,
    ) -> AsyncIterator[SalesforceQueryResponse]:
        """Lazily iterate over all pages of a SOQL query result.

        Yields one ``SalesforceQueryResponse`` per page.

        Args:
            include_deleted: When ``True``, start pagination through the
                ``/queryAll`` endpoint.

        Yields:
            ``SalesforceQueryResponse`` for each page until ``done`` is
            ``True``.

        Example::

            async for page in query_svc.query_all_iter("SELECT Id FROM Lead"):
                for record in page.records:
                    process(record)

        """
        page = await self.query(soql, include_deleted=include_deleted)
        yield page
        while not page.done and page.next_records_url:
            page = await self.query_more(page.next_records_url)
            yield page

    async def query_all(
        self,
        soql: str,
        *,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """Eagerly fetch all records across all pages of a SOQL query.

        Args:
            include_deleted: When ``True``, fetch from ``/queryAll`` so
                soft-deleted records are included.

        Returns:
            A flat list of record dicts from all pages.

        """
        records: list[dict[str, Any]] = []
        async for page in self.query_all_iter(
            soql,
            include_deleted=include_deleted,
        ):
            records.extend(page.records)
        return records


class SalesforceObjectQueryService:
    """Object-scoped SOQL query service with lightweight query composition.

    This convenience layer builds SOQL ``SELECT`` statements for one object,
    while delegating execution and pagination to ``SalesforceQueryService``.
    """

    def __init__(
        self,
        client: APIClient,
        object_name: str,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize SalesforceObjectQueryService."""
        self._query_service = SalesforceQueryService(
            client,
            api_version=api_version,
            renderer=renderer,
        )
        self._object_name = object_name

    def query(
        self,
        *,
        fields: list[str] | None = None,
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_deleted: bool = False,
    ) -> SalesforceQueryResponse:
        """Execute an object-scoped SOQL query and return the first page."""
        soql = build_select_soql(
            self._object_name,
            fields=fields,
            where=where,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return self._query_service.query(soql, include_deleted=include_deleted)

    def query_more(self, next_records_url: str) -> SalesforceQueryResponse:
        """Fetch the next page of a paginated object-scoped query result."""
        return self._query_service.query_more(next_records_url)

    def query_more_from_id(
        self,
        next_records_id: str,
        *,
        include_deleted: bool = False,
    ) -> SalesforceQueryResponse:
        """Fetch the next page using only the next-record cursor ID."""
        return self._query_service.query_more_from_id(
            next_records_id,
            include_deleted=include_deleted,
        )

    def query_updated_since(
        self,
        since: datetime,
        *,
        fields: list[str] | None = None,
        timestamp_field: str = "SystemModstamp",
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_deleted: bool = False,
    ) -> SalesforceQueryResponse:
        """Query object records updated at or after ``since``.

        Builds a ``WHERE`` clause using the provided timestamp field and
        delegates execution to ``query()``.
        """
        _validate_timestamp_field(timestamp_field)
        since_literal = _to_soql_utc_timestamp(since)
        updated_filter = f"{timestamp_field} >= '{since_literal}'"
        effective_where = f"({where}) AND {updated_filter}" if where else updated_filter
        return self.query(
            fields=fields,
            where=effective_where,
            order_by=order_by or f"{timestamp_field} ASC",
            limit=limit,
            offset=offset,
            include_deleted=include_deleted,
        )

    def query_all_iter(
        self,
        *,
        fields: list[str] | None = None,
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_deleted: bool = False,
    ) -> Iterator[SalesforceQueryResponse]:
        """Iterate lazily over all pages for an object-scoped query."""
        soql = build_select_soql(
            self._object_name,
            fields=fields,
            where=where,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return self._query_service.query_all_iter(
            soql,
            include_deleted=include_deleted,
        )

    def query_all(
        self,
        *,
        fields: list[str] | None = None,
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch all records for an object-scoped query into one list."""
        soql = build_select_soql(
            self._object_name,
            fields=fields,
            where=where,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return self._query_service.query_all(soql, include_deleted=include_deleted)


class AsyncSalesforceObjectQueryService:
    """Async object-scoped SOQL query service with lightweight composition."""

    def __init__(
        self,
        client: AsyncAPIClient,
        object_name: str,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncSalesforceObjectQueryService."""
        self._query_service = AsyncSalesforceQueryService(
            client,
            api_version=api_version,
            renderer=renderer,
        )
        self._object_name = object_name

    async def query(
        self,
        *,
        fields: list[str] | None = None,
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_deleted: bool = False,
    ) -> SalesforceQueryResponse:
        """Execute an object-scoped SOQL query and return the first page."""
        soql = build_select_soql(
            self._object_name,
            fields=fields,
            where=where,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return await self._query_service.query(soql, include_deleted=include_deleted)

    async def query_more(self, next_records_url: str) -> SalesforceQueryResponse:
        """Fetch the next page of a paginated object-scoped query result."""
        return await self._query_service.query_more(next_records_url)

    async def query_more_from_id(
        self,
        next_records_id: str,
        *,
        include_deleted: bool = False,
    ) -> SalesforceQueryResponse:
        """Fetch the next page using only the next-record cursor ID."""
        return await self._query_service.query_more_from_id(
            next_records_id,
            include_deleted=include_deleted,
        )

    async def query_updated_since(
        self,
        since: datetime,
        *,
        fields: list[str] | None = None,
        timestamp_field: str = "SystemModstamp",
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_deleted: bool = False,
    ) -> SalesforceQueryResponse:
        """Query object records updated at or after ``since``.

        Builds a ``WHERE`` clause using the provided timestamp field and
        delegates execution to ``query()``.
        """
        _validate_timestamp_field(timestamp_field)
        since_literal = _to_soql_utc_timestamp(since)
        updated_filter = f"{timestamp_field} >= '{since_literal}'"
        effective_where = f"({where}) AND {updated_filter}" if where else updated_filter
        return await self.query(
            fields=fields,
            where=effective_where,
            order_by=order_by or f"{timestamp_field} ASC",
            limit=limit,
            offset=offset,
            include_deleted=include_deleted,
        )

    async def query_all_iter(
        self,
        *,
        fields: list[str] | None = None,
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_deleted: bool = False,
    ) -> AsyncIterator[SalesforceQueryResponse]:
        """Iterate lazily over all pages for an object-scoped query."""
        soql = build_select_soql(
            self._object_name,
            fields=fields,
            where=where,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        async for page in self._query_service.query_all_iter(
            soql,
            include_deleted=include_deleted,
        ):
            yield page

    async def query_all(
        self,
        *,
        fields: list[str] | None = None,
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch all records for an object-scoped query into one list."""
        soql = build_select_soql(
            self._object_name,
            fields=fields,
            where=where,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return await self._query_service.query_all(
            soql,
            include_deleted=include_deleted,
        )
