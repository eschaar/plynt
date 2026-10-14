"""Salesforce utility REST service.

Provides sync and async services for non-SObject Salesforce Platform REST
utility endpoints such as API version discovery, organization limits,
the global SObject catalog, and Tooling API requests.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import TypeAdapter, ValidationError

from plynt.base.policies import ThrottleSignal
from plynt.base.response import Response
from plynt.connectors.salesforce.constants import (
    resolve_async_api_version,
    resolve_sync_api_version,
)
from plynt.connectors.salesforce.errors import SalesforceQueryResponseError
from plynt.connectors.salesforce.models import (
    SalesforceApiUsage,
    SalesforceApiVersion,
    SalesforceGlobalDescribeResponse,
    SalesforceLimitsResponse,
    SalesforceQueryResponse,
)
from plynt.connectors.salesforce.renderer import SalesforceRenderer
from plynt.http.client import APIClient, AsyncAPIClient
from plynt.http.renderer import Renderer
from plynt.http.service import APIService, AsyncAPIService

__all__ = [
    "AsyncSalesforceUtilityService",
    "SalesforceUtilityService",
]

_API_USAGE_RE = re.compile(r"^api-usage=(\d+)/(\d+)$")
_API_VERSION_LIST = TypeAdapter(list[SalesforceApiVersion])


def _parse_is_sandbox_response(content: bytes) -> bool:
    """Return the Organization.IsSandbox value from a Salesforce query body.

    Raises:
        SalesforceQueryResponseError: If the response is not a valid query
            payload or does not contain the expected first record shape.

    """
    try:
        result = SalesforceQueryResponse.model_validate_json(content)
    except ValidationError as exc:
        raise SalesforceQueryResponseError(
            "Salesforce query response had an invalid shape for IsSandbox lookup"
        ) from exc

    if not result.records:
        raise SalesforceQueryResponseError(
            "Salesforce query response contained no records for IsSandbox lookup"
        )

    record = result.records[0]
    if "IsSandbox" not in record:
        raise SalesforceQueryResponseError(
            "Salesforce query response missing IsSandbox in first record"
        )

    return bool(record["IsSandbox"])


def _parse_api_usage(headers: dict[str, str]) -> SalesforceApiUsage | None:
    """Parse ``api-usage`` values from the ``Sforce-Limit-Info`` header."""
    header_value: str | None = None
    for key, value in headers.items():
        if key.lower() == "sforce-limit-info":
            header_value = value
            break
    if not header_value:
        return None

    for chunk in [part.strip() for part in header_value.split(",")]:
        match = _API_USAGE_RE.match(chunk)
        if match:
            return SalesforceApiUsage(
                used=int(match.group(1)),
                limit=int(match.group(2)),
            )
    return None


def _salesforce_quota_signal(response: Response) -> ThrottleSignal | None:
    """Normalize quota exhaustion from ``Sforce-Limit-Info`` into a throttle signal.

    Reads ``Sforce-Limit-Info: api-usage=X/Y`` and returns a detected
    ``ThrottleSignal`` when used equals or exceeds the configured limit.

    Args:
        response: HTTP response to inspect.

    Returns:
        Detected ThrottleSignal when the Salesforce API quota is exhausted,
        None otherwise.

    """
    usage = _parse_api_usage(dict(response.headers))
    if usage is None or usage.limit <= 0:
        return None
    if usage.used >= usage.limit:
        return ThrottleSignal(detected=True)
    return None


class SalesforceUtilityService(APIService):
    """Service for Salesforce REST utility endpoints.

    Covers object-independent REST endpoints that do not fit the SObject CRUD
    model.
    """

    def __init__(
        self,
        client: APIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize SalesforceUtilityService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = resolve_sync_api_version(client, api_version)

    def _base_path(self) -> str:
        """Return the versioned API base path."""
        return f"/services/data/v{self._api_version}"

    def versions(self) -> list[SalesforceApiVersion]:
        """Return all Salesforce API versions available on the org.

        Calls ``GET /services/data/`` — the unversioned root endpoint that
        lists every API version the org supports, from oldest to newest.
        The last entry in the returned list is always the latest version.

        Returns:
            A list of ``SalesforceApiVersion`` entries, ordered from oldest to newest.

        Example::

            versions = utility.versions()
            latest = versions[-1]
            print(f"Latest API version: {latest.version} ({latest.label})")

        """
        resp = self._client.get("/services/data/")
        return _API_VERSION_LIST.validate_json(resp.content)

    def limits(self) -> SalesforceLimitsResponse:
        """Return current Salesforce organization limits."""
        resp = self._client.get(f"{self._base_path()}/limits")
        limits = SalesforceLimitsResponse.model_validate_json(resp.content)
        limits.set_api_usage(_parse_api_usage(resp.headers))
        return limits

    def objects(self) -> SalesforceGlobalDescribeResponse:
        """Return the global SObject catalog for the org.

        Calls ``GET /sobjects/`` and returns all SObject types available on
        the org together with their capabilities (queryable, createable, etc.).

        Returns:
            A ``SalesforceGlobalDescribeResponse`` containing all SObject types
            and their capabilities.

        Example::

            catalog = utility.objects()
            for obj in catalog.sobjects:
                if obj.queryable:
                    print(obj.name, obj.label)

        """
        resp = self._client.get(f"{self._base_path()}/sobjects/")
        return SalesforceGlobalDescribeResponse.model_validate_json(resp.content)

    def is_sandbox(self) -> bool:
        """Return whether the connected org is a sandbox.

        Queries the ``Organization`` SObject for the ``IsSandbox`` field.
        Useful as a guard before executing destructive or production-only
        operations.

        Returns:
            ``True`` when the org is a sandbox, ``False`` for a production org.

        """
        resp = self._client.get(
            f"{self._base_path()}/query",
            params={"q": "SELECT IsSandbox FROM Organization LIMIT 1"},
        )
        return _parse_is_sandbox_response(resp.content)

    def search(self, sosl: str) -> None:
        """Removed — use ``SalesforceSearchService.search()`` instead."""
        raise NotImplementedError(
            "search() has been moved to SalesforceSearchService. "
            "Use facade.search().search(sosl) instead."
        )

    def quick_search(self, search_text: str) -> None:
        """Removed — use ``SalesforceSearchService.quick_search()`` instead."""
        raise NotImplementedError(
            "quick_search() has been moved to SalesforceSearchService. "
            "Use facade.search().quick_search(text) instead."
        )

    def tooling_execute(
        self,
        action: str,
        *,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Call a Salesforce Tooling REST endpoint.

        Args:
            action: Tooling API endpoint path suffix (e.g. ``"query"``).
            method: HTTP method (default ``"GET"``).
            data: Optional JSON body for write requests.
            params: Optional query parameters.

        Returns:
            Parsed JSON response, or ``None`` when no response body exists.

        """
        resp = self._client.request(
            method,
            f"{self._base_path()}/tooling/{action.lstrip('/')}",
            content=self._renderer.render(data) if data is not None else None,
            params=params,
        )
        if not resp.content:
            return None
        return json.loads(resp.content)

    def restful(
        self,
        path: str,
        *,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        versioned: bool = True,
    ) -> Any:
        """Call an arbitrary Salesforce REST endpoint as an escape hatch."""
        target_path = (
            f"{self._base_path()}/{path.lstrip('/')}"
            if versioned
            else f"/{path.lstrip('/')}"
        )
        resp = self._client.request(
            method,
            target_path,
            headers=headers,
            params=params,
            content=self._renderer.render(data) if data is not None else None,
        )
        if not resp.content:
            return None
        return json.loads(resp.content)

    def restful_unversioned(
        self,
        path: str,
        *,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Call an arbitrary Salesforce REST endpoint without API version prefix."""
        return self.restful(
            path,
            method=method,
            data=data,
            params=params,
            headers=headers,
            versioned=False,
        )


class AsyncSalesforceUtilityService(AsyncAPIService):
    """Async service for Salesforce REST utility endpoints."""

    def __init__(
        self,
        client: AsyncAPIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncSalesforceUtilityService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = api_version

    async def _base_path(self) -> str:
        """Return the versioned API base path."""
        if self._api_version is None:
            self._api_version = await resolve_async_api_version(
                self._client,
                self._api_version,
            )
        return f"/services/data/v{self._api_version}"

    async def versions(self) -> list[SalesforceApiVersion]:
        """Return all Salesforce API versions available on the org.

        Calls ``GET /services/data/`` — the unversioned root endpoint that
        lists every API version the org supports, from oldest to newest.
        The last entry in the returned list is always the latest version.

        Returns:
            A list of ``SalesforceApiVersion`` entries, ordered from oldest to newest.

        """
        resp = await self._client.get("/services/data/")
        return _API_VERSION_LIST.validate_json(resp.content)

    async def limits(self) -> SalesforceLimitsResponse:
        """Return current Salesforce organization limits."""
        resp = await self._client.get(f"{await self._base_path()}/limits")
        limits = SalesforceLimitsResponse.model_validate_json(resp.content)
        limits.set_api_usage(_parse_api_usage(resp.headers))
        return limits

    async def objects(self) -> SalesforceGlobalDescribeResponse:
        """Return the global SObject catalog for the org.

        Calls ``GET /sobjects/`` and returns all SObject types available on
        the org together with their capabilities.

        Returns:
            A ``SalesforceGlobalDescribeResponse`` containing all SObject types.

        """
        resp = await self._client.get(f"{await self._base_path()}/sobjects/")
        return SalesforceGlobalDescribeResponse.model_validate_json(resp.content)

    async def is_sandbox(self) -> bool:
        """Return whether the connected org is a sandbox.

        Queries the ``Organization`` SObject for the ``IsSandbox`` field.
        Useful as a guard before executing destructive or production-only
        operations.

        Returns:
            ``True`` when the org is a sandbox, ``False`` for a production org.

        """
        base = await self._base_path()
        resp = await self._client.get(
            f"{base}/query",
            params={"q": "SELECT IsSandbox FROM Organization LIMIT 1"},
        )
        return _parse_is_sandbox_response(resp.content)

    async def search(self, sosl: str) -> None:
        """Removed — use ``AsyncSalesforceSearchService.search()`` instead."""
        raise NotImplementedError(
            "search() has been moved to AsyncSalesforceSearchService. "
            "Use facade.search().search(sosl) instead."
        )

    async def quick_search(self, search_text: str) -> None:
        """Removed — use ``AsyncSalesforceSearchService.quick_search()`` instead."""
        raise NotImplementedError(
            "quick_search() has been moved to AsyncSalesforceSearchService. "
            "Use facade.search().quick_search(text) instead."
        )

    async def tooling_execute(
        self,
        action: str,
        *,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Call a Salesforce Tooling REST endpoint."""
        base_path = await self._base_path()
        resp = await self._client.request(
            method,
            f"{base_path}/tooling/{action.lstrip('/')}",
            content=self._renderer.render(data) if data is not None else None,
            params=params,
        )
        if not resp.content:
            return None
        return json.loads(resp.content)

    async def restful(
        self,
        path: str,
        *,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        versioned: bool = True,
    ) -> Any:
        """Call an arbitrary Salesforce REST endpoint as an escape hatch."""
        base_path = await self._base_path()
        target_path = (
            f"{base_path}/{path.lstrip('/')}" if versioned else f"/{path.lstrip('/')}"
        )
        resp = await self._client.request(
            method,
            target_path,
            headers=headers,
            params=params,
            content=self._renderer.render(data) if data is not None else None,
        )
        if not resp.content:
            return None
        return json.loads(resp.content)

    async def restful_unversioned(
        self,
        path: str,
        *,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Call an arbitrary Salesforce REST endpoint without API version prefix."""
        return await self.restful(
            path,
            method=method,
            data=data,
            params=params,
            headers=headers,
            versioned=False,
        )
