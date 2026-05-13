"""Salesforce API client for Plynth.

Provides ``SalesforceAPIClient`` and ``AsyncSalesforceAPIClient``, which
extend ``APIClient`` / ``AsyncAPIClient`` to use the org-specific
``instance_url`` returned in the Salesforce OAuth2 token response as the
base URL for all API calls, rather than a static URL configured at
construction time.

Usage::

    from plynth.http.transport import HttpxSyncTransport
    from plynth.connectors.salesforce.auth import (
        SalesforceClientCredentialsAuthMiddleware,
    )
    from plynth.connectors.salesforce.client import SalesforceAPIClient
    from plynth.connectors.salesforce.facade import SalesforceAPIFacade

    auth = SalesforceClientCredentialsAuthMiddleware(
        client_id="3MVG9...",
        client_secret="abc123",
        token_url="https://login.salesforce.com/services/oauth2/token",
    )
    transport = HttpxSyncTransport(middlewares=[auth])
    client = SalesforceAPIClient(auth=auth, transport=transport)
    facade = SalesforceAPIFacade(client)
    svc = facade.sobject("Account")

"""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any

from plynth.base.request import Request
from plynth.base.response import Response
from plynth.base.transport import AsyncTransport, SyncTransport
from plynth.connectors.salesforce.auth import (
    AsyncSalesforceClientCredentialsAuthMiddleware,
    AsyncSalesforcePasswordAuthMiddleware,
    AsyncSalesforceSessionAuthMiddleware,
    SalesforceClientCredentialsAuthMiddleware,
    SalesforcePasswordAuthMiddleware,
    SalesforceSessionAuthMiddleware,
)
from plynth.connectors.salesforce.constants import DEFAULT_API_VERSION
from plynth.http.client import APIClient, AsyncAPIClient

__all__ = ["AsyncSalesforceAPIClient", "SalesforceAPIClient"]


class SalesforceAPIClient(APIClient):
    """Salesforce REST API client with dynamic instance URL resolution.

    Extends ``APIClient`` (which adds JSON headers and typed error raising)
    to replace the static ``base_url`` with the org-specific ``instance_url``
    returned in the Salesforce OAuth2 token response.

    The ``instance_url`` is fetched lazily on the first request and cached
    alongside the access token by
    ``SalesforceClientCredentialsAuthMiddleware``.
    Subsequent requests use the cached value at no extra cost. When the token
    is invalidated (e.g. on a 401), both the token and the ``instance_url``
    are refreshed together on the next request.

    Args:
        auth: Salesforce OAuth2 auth middleware. Passed to both this client
            (for URL resolution) and wired into the transport's middleware
            list (for auth headers). The same instance must be used in both.

    Example::

        auth = SalesforceClientCredentialsAuthMiddleware(
            client_id="3MVG9...",
            client_secret="abc123",
            token_url="https://login.salesforce.com/services/oauth2/token",
        )
        transport = HttpxSyncTransport(middlewares=[auth])
        client = SalesforceAPIClient(auth=auth, transport=transport)

    """

    def __init__(
        self,
        auth: (
            SalesforceClientCredentialsAuthMiddleware
            | SalesforcePasswordAuthMiddleware
            | SalesforceSessionAuthMiddleware
        ),
        transport: SyncTransport,
        headers: dict[str, str] | None = None,
        api_version: str | None = None,
    ) -> None:
        # base_url is not used for API calls; instance_url is resolved from auth.
        """Initialize SalesforceAPIClient."""
        super().__init__(base_url="", transport=transport, headers=headers)
        self._sf_auth = auth
        self._configured_api_version = api_version
        self._resolved_api_version: str | None = None

    @property
    def api_version(self) -> str:
        """Return the configured or lazily discovered Salesforce API version."""
        if self._configured_api_version:
            return self._configured_api_version
        if self._resolved_api_version:
            return self._resolved_api_version

        response = self.get("/services/data/")
        payload = json.loads(response.content)
        if not isinstance(payload, list) or not payload:
            return DEFAULT_API_VERSION

        latest = payload[-1]
        if isinstance(latest, dict):
            version = latest.get("version")
            if isinstance(version, str) and version:
                self._resolved_api_version = version
                return version
        return DEFAULT_API_VERSION

    def _build_request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> Request:
        """Build a request using the org-specific Salesforce instance URL."""
        instance_url = self._sf_auth.instance_url
        merged_headers = {**self._default_headers, **(headers or {})}
        return Request(
            method=method,
            url=f"{instance_url}/{path.lstrip('/')}",
            headers=merged_headers,
            params=params or {},
            content=content,
        )

    def build_request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> Request:
        """Public wrapper for request construction used by white-box tests."""
        return self._build_request(
            method,
            path,
            headers=headers,
            params=params,
            content=content,
        )

    def set_configured_api_version(self, api_version: str | None) -> None:
        """Set a fixed API version value for this client instance."""
        self._configured_api_version = api_version

    def set_resolved_api_version(self, api_version: str | None) -> None:
        """Set the cached dynamically discovered API version value."""
        self._resolved_api_version = api_version

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> Response:
        """Send a request and raise a typed Salesforce or HTTP error.

        Builds the request using ``instance_url`` (not the empty ``base_url``)
        so that any raised ``HttpStatusError`` reports the full Salesforce URL
        rather than a bare path, making error diagnostics accurate.

        Returns:
            The raw transport response (status 1xx-3xx).

        Raises:
            SalesforceAPIError: (or subclass) for Salesforce business-logic
                errors (``REQUIRED_FIELD_MISSING``, ``DUPLICATE_VALUE``, …).
            HttpStatusError: For non-Salesforce HTTP errors.

        """
        from plynth.connectors.salesforce.errors import raise_for_salesforce_errors
        from plynth.http.errors import HttpStatusError, match_error

        req = self._build_request(
            method,
            path,
            headers=headers,
            params=params,
            content=content,
        )
        resp = self._transport.send(req)
        if resp.status_code >= HTTPStatus.BAD_REQUEST:
            raise_for_salesforce_errors(resp)
            err = match_error(resp.status_code, method=method, url=req.url)
            if isinstance(err, HttpStatusError):
                err.attach_response(resp)
            raise err
        return resp


class AsyncSalesforceAPIClient(AsyncAPIClient):
    """Async Salesforce REST API client with dynamic instance URL resolution.

    Async counterpart of ``SalesforceAPIClient``. Extends ``AsyncAPIClient``
    (which adds JSON headers and typed error raising) to replace the static
    ``base_url`` with the org-specific ``instance_url`` returned in the
    Salesforce OAuth2 token response.

    The ``instance_url`` is fetched lazily on the first request and cached
    alongside the access token by
    ``AsyncSalesforceClientCredentialsAuthMiddleware``.
    Subsequent requests use the cached value at no extra cost.

    Args:
        auth: Async Salesforce OAuth2 auth middleware. Passed to both this
            client (for URL resolution) and wired into the transport's
            middleware list (for auth headers). The same instance must be
            used in both.

    Example::

        auth = AsyncSalesforceClientCredentialsAuthMiddleware(
            client_id="3MVG9...",
            client_secret="abc123",
            token_url="https://login.salesforce.com/services/oauth2/token",
        )
        transport = HttpxAsyncTransport(middlewares=[auth])
        client = AsyncSalesforceAPIClient(auth=auth, transport=transport)

    """

    def __init__(
        self,
        auth: (
            AsyncSalesforceClientCredentialsAuthMiddleware
            | AsyncSalesforcePasswordAuthMiddleware
            | AsyncSalesforceSessionAuthMiddleware
        ),
        transport: AsyncTransport,
        headers: dict[str, str] | None = None,
        api_version: str | None = None,
    ) -> None:
        # base_url is not used for API calls; instance_url is resolved from auth.
        """Initialize AsyncSalesforceAPIClient."""
        super().__init__(base_url="", transport=transport, headers=headers)
        self._sf_auth = auth
        self._configured_api_version = api_version
        self._resolved_api_version: str | None = None

    @property
    def api_version(self) -> str:
        """Return configured or cached API version for async clients."""
        if self._configured_api_version:
            return self._configured_api_version
        if self._resolved_api_version:
            return self._resolved_api_version
        return DEFAULT_API_VERSION

    async def get_api_version(self) -> str:
        """Return configured or lazily discovered Salesforce API version."""
        if self._configured_api_version:
            return self._configured_api_version
        if self._resolved_api_version:
            return self._resolved_api_version

        response = await self.get("/services/data/")
        payload = json.loads(response.content)
        if not isinstance(payload, list) or not payload:
            return DEFAULT_API_VERSION

        latest = payload[-1]
        if isinstance(latest, dict):
            version = latest.get("version")
            if isinstance(version, str) and version:
                self._resolved_api_version = version
                return version
        return DEFAULT_API_VERSION

    def set_configured_api_version(self, api_version: str | None) -> None:
        """Set a fixed API version value for this client instance."""
        self._configured_api_version = api_version

    def set_resolved_api_version(self, api_version: str | None) -> None:
        """Set the cached dynamically discovered API version value."""
        self._resolved_api_version = api_version

    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> Response:
        """Send a request using the Salesforce instance URL as base.

        Resolves ``instance_url`` from the authenticator asynchronously
        (fetching a token first if needed) and uses it instead of the static
        ``base_url``.

        Returns:
            The raw transport response (status 1xx-3xx).

        Raises:
            HttpStatusError: Typed subclass for the specific status code.

        """
        from plynth.connectors.salesforce.errors import raise_for_salesforce_errors
        from plynth.http.errors import HttpStatusError, match_error

        instance_url = await self._sf_auth.get_instance_url()
        merged_headers = {**self._default_headers, **(headers or {})}
        req = Request(
            method=method,
            url=f"{instance_url}/{path.lstrip('/')}",
            headers=merged_headers,
            params=params or {},
            content=content,
        )
        resp = await self._transport.send(req)
        if resp.status_code >= HTTPStatus.BAD_REQUEST:
            raise_for_salesforce_errors(resp)
            err = match_error(resp.status_code, method=method, url=req.url)
            if isinstance(err, HttpStatusError):
                err.attach_response(resp)
            raise err
        return resp
