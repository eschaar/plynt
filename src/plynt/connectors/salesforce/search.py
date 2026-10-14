"""Salesforce SOSL search service.

Provides sync and async services for Salesforce SOSL (Salesforce Object
Search Language) search endpoints.
"""

from __future__ import annotations

import asyncio

from plynt.connectors.salesforce.constants import (
    resolve_async_api_version,
    resolve_sync_api_version,
)
from plynt.connectors.salesforce.models import SalesforceSearchResponse
from plynt.connectors.salesforce.renderer import SalesforceRenderer
from plynt.http.client import APIClient, AsyncAPIClient
from plynt.http.renderer import Renderer
from plynt.http.service import APIService, AsyncAPIService

__all__ = [
    "AsyncSalesforceSearchService",
    "SalesforceSearchService",
]


class SalesforceSearchService(APIService):
    """Service for Salesforce SOSL search endpoints.

    Wraps the ``/search`` endpoint for full-text search across multiple
    SObject types using SOSL (Salesforce Object Search Language).

    Use ``escape_sosl()`` from ``plynt.connectors.salesforce.helpers`` to safely
    escape user-supplied search terms before embedding them in a SOSL string.
    """

    def __init__(
        self,
        client: APIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize SalesforceSearchService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = resolve_sync_api_version(client, api_version)

    def _base_path(self) -> str:
        """Return the versioned Salesforce REST API base path."""
        return f"/services/data/v{self._api_version}"

    def search(self, sosl: str) -> SalesforceSearchResponse:
        """Execute a SOSL query via ``GET /search``.

        Args:
            sosl: A full SOSL string, for example
                ``"FIND {Acme} IN NAME FIELDS RETURNING Account(Id, Name)"``.

        Example::

            svc = facade.search()
            response = svc.search(
                "FIND {Acme} IN NAME FIELDS RETURNING Account(Id, Name)"
            )
            for record in response.search_records:
                print(record.sobject_type, record.id)

        """
        resp = self._client.get(
            f"{self._base_path()}/search",
            params={"q": sosl},
        )
        return SalesforceSearchResponse.model_validate_json(resp.content)

    def quick_search(self, search_text: str) -> SalesforceSearchResponse:
        """Execute a simple keyword search wrapped in SOSL ``FIND`` syntax.

        Convenience wrapper around ``search()`` for cases where only a
        bare search term is needed across all searchable fields and objects.

        Args:
            search_text: The search term. Special SOSL characters are *not*
                escaped automatically — call ``escape_sosl()`` first when
                ``search_text`` is user-supplied.

        """
        return self.search(f"FIND {{{search_text}}}")


class AsyncSalesforceSearchService(AsyncAPIService):
    """Async service for Salesforce SOSL search endpoints."""

    def __init__(
        self,
        client: AsyncAPIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncSalesforceSearchService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = api_version
        self._version_lock = asyncio.Lock()

    async def _base_path(self) -> str:
        """Return the versioned Salesforce REST API base path."""
        if self._api_version is None:
            async with self._version_lock:
                if self._api_version is None:
                    self._api_version = await resolve_async_api_version(
                        self._client,
                        self._api_version,
                    )
        return f"/services/data/v{self._api_version}"

    async def search(self, sosl: str) -> SalesforceSearchResponse:
        """Execute a SOSL query via ``GET /search``."""
        base_path = await self._base_path()
        resp = await self._client.get(
            f"{base_path}/search",
            params={"q": sosl},
        )
        return SalesforceSearchResponse.model_validate_json(resp.content)

    async def quick_search(self, search_text: str) -> SalesforceSearchResponse:
        """Execute a simple keyword search wrapped in SOSL ``FIND`` syntax.

        Args:
            search_text: The search term. Special SOSL characters are *not*
                escaped automatically — call ``escape_sosl()`` first when
                ``search_text`` is user-supplied.

        """
        return await self.search(f"FIND {{{search_text}}}")
