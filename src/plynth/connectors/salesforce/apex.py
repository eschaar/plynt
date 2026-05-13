"""Salesforce Apex REST convenience services."""

from __future__ import annotations

import json
from typing import Any

from plynth.connectors.salesforce.renderer import SalesforceRenderer
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import Renderer
from plynth.http.service import APIService, AsyncAPIService

__all__ = [
    "AsyncSalesforceApexRestService",
    "SalesforceApexRestService",
]


class SalesforceApexRestService(APIService):
    """Convenience service for Salesforce Apex REST endpoints."""

    def __init__(
        self,
        client: APIClient,
        *,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize SalesforceApexRestService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())

    def _path(self, action: str) -> str:
        """Build an Apex REST endpoint path."""
        return f"/services/apexrest/{action.lstrip('/')}"

    def execute(
        self,
        action: str,
        *,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Execute an Apex REST request and return parsed JSON or None."""
        resp = self._client.request(
            method,
            self._path(action),
            headers=headers,
            params=params,
            content=self._renderer.render(data) if data is not None else None,
        )
        if not resp.content:
            return None
        return json.loads(resp.content)


class AsyncSalesforceApexRestService(AsyncAPIService):
    """Async convenience service for Salesforce Apex REST endpoints."""

    def __init__(
        self,
        client: AsyncAPIClient,
        *,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncSalesforceApexRestService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())

    def _path(self, action: str) -> str:
        """Build an Apex REST endpoint path."""
        return f"/services/apexrest/{action.lstrip('/')}"

    async def execute(
        self,
        action: str,
        *,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Execute an Apex REST request and return parsed JSON or None."""
        resp = await self._client.request(
            method,
            self._path(action),
            headers=headers,
            params=params,
            content=self._renderer.render(data) if data is not None else None,
        )
        if not resp.content:
            return None
        return json.loads(resp.content)
