# pyright: reportPrivateUsage=false
# pylint: disable=protected-access
"""Tests for SalesforceAPIClient and AsyncSalesforceAPIClient."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from plynth.base.request import Request
from plynth.connectors.salesforce.auth import (
    AsyncSalesforceClientCredentialsAuthMiddleware,
    AsyncSalesforcePasswordAuthMiddleware,
    AsyncSalesforceSessionAuthMiddleware,
    SalesforceClientCredentialsAuthMiddleware,
    SalesforcePasswordAuthMiddleware,
    SalesforceSessionAuthMiddleware,
)
from plynth.connectors.salesforce.client import (
    AsyncSalesforceAPIClient,
    SalesforceAPIClient,
)
from plynth.connectors.salesforce.constants import DEFAULT_API_VERSION
from plynth.connectors.salesforce.errors import (
    SalesforceAPIError,
    SalesforceDuplicateError,
    SalesforceValidationError,
)
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.errors import NotFoundError, UnauthorizedError
from plynth.http.renderer import JSONRenderer
from tests.conftest import MockAsyncTransport, MockSyncTransport

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INSTANCE_URL = "https://myorg.my.salesforce.com"
SERVICE_PATH = "/services/data/v59.0/sobjects/Account"
_JSON_RENDERER = JSONRenderer()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(
    instance_url: str = INSTANCE_URL,
    status_code: int = 200,
    content: bytes = b"{}",
    extra_headers: dict[str, str] | None = None,
) -> tuple[
    SalesforceAPIClient,
    SalesforceClientCredentialsAuthMiddleware,
    MockSyncTransport,
]:
    """Build a ``SalesforceAPIClient`` with mocked auth and transport."""
    auth = MagicMock(spec=SalesforceClientCredentialsAuthMiddleware)
    auth.instance_url = instance_url
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = SalesforceAPIClient(auth=auth, transport=transport, headers=extra_headers)
    return client, auth, transport


def _make_password_client(
    instance_url: str = INSTANCE_URL,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[
    SalesforceAPIClient,
    SalesforcePasswordAuthMiddleware,
    MockSyncTransport,
]:
    """Build a ``SalesforceAPIClient`` with password-flow auth mock."""
    auth = MagicMock(spec=SalesforcePasswordAuthMiddleware)
    auth.instance_url = instance_url
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = SalesforceAPIClient(auth=auth, transport=transport)
    return client, auth, transport


def _json_bytes(data: Any) -> bytes:
    """Render test payloads to JSON bytes via the shared renderer layer."""
    return _JSON_RENDERER.render(data)


# ---------------------------------------------------------------------------
# TestSalesforceAPIClient
# ---------------------------------------------------------------------------


class TestSalesforceAPIClient:
    """Verify SalesforceAPIClient._build_request and inheritance."""

    def test_inherits_from_api_client(self) -> None:
        """Validate inherits from api client."""
        client, _, _ = _make_client()
        assert isinstance(client, APIClient)

    def test_build_request_uses_instance_url(self) -> None:
        """Validate build request uses instance url."""
        client, _, _ = _make_client()
        req = client.build_request("GET", SERVICE_PATH)
        assert req.url == f"{INSTANCE_URL}/{SERVICE_PATH.lstrip('/')}"

    def test_build_request_strips_leading_slash_from_path(self) -> None:
        """Validate build request strips leading slash from path."""
        client, _, _ = _make_client()
        req_with = client.build_request("GET", "/some/path")
        req_without = client.build_request("GET", "some/path")
        assert req_with.url == req_without.url

    def test_build_request_preserves_path_without_leading_slash(self) -> None:
        """Validate build request preserves path without leading slash."""
        client, _, _ = _make_client()
        req = client.build_request("GET", "services/data")
        assert req.url == f"{INSTANCE_URL}/services/data"

    def test_build_request_includes_default_json_headers(self) -> None:
        """Validate build request includes default json headers."""
        client, _, _ = _make_client()
        req = client.build_request("GET", SERVICE_PATH)
        assert req.headers.get("Content-Type") == "application/json"
        assert req.headers.get("Accept") == "application/json"

    def test_build_request_merges_per_call_headers(self) -> None:
        """Validate build request merges per call headers."""
        client, _, _ = _make_client()
        req = client.build_request("GET", SERVICE_PATH, headers={"X-Custom": "value"})
        assert req.headers.get("X-Custom") == "value"
        assert req.headers.get("Accept") == "application/json"

    def test_per_call_headers_override_defaults(self) -> None:
        """Validate per call headers override defaults."""
        client, _, _ = _make_client()
        req = client.build_request(
            "GET", SERVICE_PATH, headers={"Accept": "text/plain"}
        )
        assert req.headers.get("Accept") == "text/plain"

    def test_extra_default_headers_merged_from_constructor(self) -> None:
        """Validate extra default headers merged from constructor."""
        client, _, _ = _make_client(extra_headers={"X-Org": "myorg"})
        req = client.build_request("GET", SERVICE_PATH)
        assert req.headers.get("X-Org") == "myorg"

    def test_build_request_passes_params(self) -> None:
        """Validate build request passes params."""
        client, _, _ = _make_client()
        req = client.build_request("GET", SERVICE_PATH, params={"fields": "Id,Name"})
        assert req.params == {"fields": "Id,Name"}

    def test_build_request_empty_params_when_none(self) -> None:
        """Validate build request empty params when none."""
        client, _, _ = _make_client()
        req = client.build_request("GET", SERVICE_PATH)
        assert req.params == {}

    def test_build_request_passes_content(self) -> None:
        """Validate build request passes content."""
        client, _, _ = _make_client()
        body = b'{"Name": "Acme"}'
        req = client.build_request("POST", SERVICE_PATH, content=body)
        assert req.content == body

    def test_build_request_reads_instance_url_from_auth(self) -> None:
        """instance_url is resolved via the auth object on every call."""
        auth = MagicMock(spec=SalesforceClientCredentialsAuthMiddleware)
        auth.instance_url = INSTANCE_URL
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = SalesforceAPIClient(auth=auth, transport=transport)
        first = client.build_request("GET", SERVICE_PATH)

        auth.instance_url = "https://new-org.my.salesforce.com"
        second = client.build_request("GET", SERVICE_PATH)

        assert first.url != second.url

    def test_get_uses_instance_url_in_full_request(self) -> None:
        """An end-to-end call uses the instance URL in the final transport send."""
        client, _, transport = _make_client(content=b'{"Id": "123"}')
        client.get(SERVICE_PATH)
        sent: Request = transport.send.call_args[0][0]
        assert sent.url.startswith(INSTANCE_URL)

    def test_different_instance_urls_produce_different_request_urls(self) -> None:
        """Validate different instance urls produce different request urls."""
        client_a, _, _ = _make_client(instance_url="https://org-a.my.salesforce.com")
        client_b, _, _ = _make_client(instance_url="https://org-b.my.salesforce.com")
        req_a = client_a.build_request("GET", "/path")
        req_b = client_b.build_request("GET", "/path")
        assert req_a.url != req_b.url

    def test_accepts_password_auth_middleware(self) -> None:
        """Validate accepts password auth middleware."""
        client, _, transport = _make_password_client(content=b'{"Id": "123"}')
        client.get(SERVICE_PATH)
        sent: Request = transport.send.call_args[0][0]
        assert sent.url.startswith(INSTANCE_URL)

    def test_accepts_session_auth_middleware(self) -> None:
        """Validate client works with direct session/token auth middleware."""
        auth = SalesforceSessionAuthMiddleware(
            access_token="token-123",
            instance_url=INSTANCE_URL,
        )
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = SalesforceAPIClient(auth=auth, transport=transport)

        client.get(SERVICE_PATH)
        sent: Request = transport.send.call_args[0][0]
        assert sent.url.startswith(INSTANCE_URL)

    def test_api_version_discovers_latest_from_versions_endpoint(self) -> None:
        """Validate api version discovery reads latest entry from /services/data/."""
        payload = _json_bytes(
            [
                {"label": "v62", "url": "/services/data/v62.0", "version": "62.0"},
                {"label": "v63", "url": "/services/data/v63.0", "version": "63.0"},
            ]
        )
        client, _, transport = _make_client(content=payload)

        assert client.api_version == "63.0"
        sent: Request = transport.send.call_args[0][0]
        assert sent.url.endswith("/services/data/")

    def test_api_version_is_cached_after_first_discovery(self) -> None:
        """Validate api version discovery result is cached on the client."""
        payload = _json_bytes(
            [{"label": "v63", "url": "/services/data/v63.0", "version": "63.0"}]
        )
        client, _, transport = _make_client(content=payload)

        assert client.api_version == "63.0"
        assert client.api_version == "63.0"
        assert transport.send.call_count == 1

    def test_api_version_uses_configured_value_without_discovery_call(self) -> None:
        """Validate configured api version bypasses discovery request."""
        client, _, transport = _make_client(content=_json_bytes([]))
        client.set_configured_api_version("61.0")

        assert client.api_version == "61.0"
        assert transport.send.call_count == 0

    def test_api_version_falls_back_to_default_on_invalid_discovery_payload(
        self,
    ) -> None:
        """Validate invalid discovery payload falls back to DEFAULT_API_VERSION."""
        client, _, _ = _make_client(content=_json_bytes({"unexpected": "shape"}))

        assert client.api_version == DEFAULT_API_VERSION

    def test_api_version_falls_back_to_default_when_latest_has_no_version(self) -> None:
        """Validate discovery fallback when latest item lacks version field."""
        payload = _json_bytes([{"label": "vLatest", "url": "/services/data/v99.0"}])
        client, _, _ = _make_client(content=payload)

        assert client.api_version == DEFAULT_API_VERSION


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------


def _make_async_client(
    instance_url: str = INSTANCE_URL,
    status_code: int = 200,
    content: bytes = b"{}",
    extra_headers: dict[str, str] | None = None,
) -> tuple[
    AsyncSalesforceAPIClient,
    AsyncSalesforceClientCredentialsAuthMiddleware,
    MockAsyncTransport,
]:
    """Build an ``AsyncSalesforceAPIClient`` with mocked auth and transport."""
    auth = MagicMock(spec=AsyncSalesforceClientCredentialsAuthMiddleware)
    auth.get_instance_url = AsyncMock(return_value=instance_url)
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncSalesforceAPIClient(
        auth=auth, transport=transport, headers=extra_headers
    )
    return client, auth, transport


def _make_async_password_client(
    instance_url: str = INSTANCE_URL,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[
    AsyncSalesforceAPIClient,
    AsyncSalesforcePasswordAuthMiddleware,
    MockAsyncTransport,
]:
    """Build an ``AsyncSalesforceAPIClient`` with password-flow auth mock."""
    auth = MagicMock(spec=AsyncSalesforcePasswordAuthMiddleware)
    auth.get_instance_url = AsyncMock(return_value=instance_url)
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncSalesforceAPIClient(auth=auth, transport=transport)
    return client, auth, transport


# ---------------------------------------------------------------------------
# TestAsyncSalesforceAPIClient
# ---------------------------------------------------------------------------


class TestAsyncSalesforceAPIClient:
    """Verify AsyncSalesforceAPIClient.request and inheritance."""

    def test_inherits_from_async_api_client(self) -> None:
        """Validate inherits from async api client."""
        client, _, _ = _make_async_client()
        assert isinstance(client, AsyncAPIClient)

    async def test_request_uses_instance_url_from_auth(self) -> None:
        """Validate request uses instance url from auth."""
        client, _, transport = _make_async_client(content=b'{"Id": "123"}')
        await client.get(SERVICE_PATH)
        sent: Request = transport.send.call_args[0][0]
        assert sent.url.startswith(INSTANCE_URL)

    async def test_request_strips_leading_slash_from_path(self) -> None:
        """Validate request strips leading slash from path."""
        client, _, transport = _make_async_client()
        await client.get("/some/path")
        sent: Request = transport.send.call_args[0][0]
        assert sent.url == f"{INSTANCE_URL}/some/path"

    async def test_request_preserves_path_without_leading_slash(self) -> None:
        """Validate request preserves path without leading slash."""
        client, _, transport = _make_async_client()
        await client.get("some/path")
        sent: Request = transport.send.call_args[0][0]
        assert sent.url == f"{INSTANCE_URL}/some/path"

    async def test_request_includes_default_json_headers(self) -> None:
        """Validate request includes default json headers."""
        client, _, transport = _make_async_client()
        await client.get(SERVICE_PATH)
        sent: Request = transport.send.call_args[0][0]
        assert sent.headers.get("Content-Type") == "application/json"
        assert sent.headers.get("Accept") == "application/json"

    async def test_request_merges_per_call_headers(self) -> None:
        """Validate request merges per call headers."""
        client, _, transport = _make_async_client()
        await client.get(SERVICE_PATH, headers={"X-Custom": "value"})
        sent: Request = transport.send.call_args[0][0]
        assert sent.headers.get("X-Custom") == "value"
        assert sent.headers.get("Accept") == "application/json"

    async def test_request_merges_constructor_headers(self) -> None:
        """Validate request merges constructor headers."""
        client, _, transport = _make_async_client(extra_headers={"X-Org": "myorg"})
        await client.get(SERVICE_PATH)
        sent: Request = transport.send.call_args[0][0]
        assert sent.headers.get("X-Org") == "myorg"

    async def test_request_passes_params(self) -> None:
        """Validate request passes params."""
        client, _, transport = _make_async_client()
        await client.get(SERVICE_PATH, params={"fields": "Id,Name"})
        sent: Request = transport.send.call_args[0][0]
        assert sent.params == {"fields": "Id,Name"}

    async def test_request_resolves_instance_url_via_auth(self) -> None:
        """The URL in the request comes from auth.get_instance_url, not base_url."""
        custom_url = "https://specific-org.my.salesforce.com"
        client, _, transport = _make_async_client(instance_url=custom_url)
        await client.get(SERVICE_PATH)
        sent: Request = transport.send.call_args[0][0]
        assert sent.url.startswith(custom_url)

    async def test_request_raises_not_found_on_404(self) -> None:
        """Validate request raises not found on 404."""
        client, _, _ = _make_async_client(status_code=404)
        with pytest.raises(NotFoundError):
            await client.get(SERVICE_PATH)

    async def test_different_instance_urls_produce_different_request_urls(
        self,
    ) -> None:
        """Validate different instance urls produce different request urls."""
        client_a, _, transport_a = _make_async_client(
            instance_url="https://org-a.my.salesforce.com"
        )
        client_b, _, transport_b = _make_async_client(
            instance_url="https://org-b.my.salesforce.com"
        )
        await client_a.get("/path")
        await client_b.get("/path")
        url_a: str = transport_a.send.call_args[0][0].url
        url_b: str = transport_b.send.call_args[0][0].url
        assert url_a != url_b

    async def test_accepts_async_password_auth_middleware(self) -> None:
        """Validate accepts async password auth middleware."""
        client, _, transport = _make_async_password_client(content=b'{"Id": "123"}')
        await client.get(SERVICE_PATH)
        sent: Request = transport.send.call_args[0][0]
        assert sent.url.startswith(INSTANCE_URL)

    async def test_accepts_async_session_auth_middleware(self) -> None:
        """Validate async client works with direct session/token middleware."""
        auth = AsyncSalesforceSessionAuthMiddleware(
            access_token="token-123",
            instance_url=INSTANCE_URL,
        )
        transport = MockAsyncTransport(status_code=200, content=b"{}")
        client = AsyncSalesforceAPIClient(auth=auth, transport=transport)

        await client.get(SERVICE_PATH)
        sent: Request = transport.send.call_args[0][0]
        assert sent.url.startswith(INSTANCE_URL)

    async def test_get_api_version_discovers_latest_from_versions_endpoint(
        self,
    ) -> None:
        """Validate async api version discovery reads latest /services/data/ entry."""
        payload = _json_bytes(
            [
                {"label": "v62", "url": "/services/data/v62.0", "version": "62.0"},
                {"label": "v64", "url": "/services/data/v64.0", "version": "64.0"},
            ]
        )
        client, _, transport = _make_async_client(content=payload)

        assert await client.get_api_version() == "64.0"
        sent: Request = transport.send.call_args[0][0]
        assert sent.url.endswith("/services/data/")

    async def test_get_api_version_is_cached_after_first_discovery(self) -> None:
        """Validate async api version discovery is cached on subsequent calls."""
        payload = _json_bytes(
            [{"label": "v63", "url": "/services/data/v63.0", "version": "63.0"}]
        )
        client, _, transport = _make_async_client(content=payload)

        assert await client.get_api_version() == "63.0"
        assert await client.get_api_version() == "63.0"
        assert transport.send.call_count == 1

    def test_async_api_version_property_uses_configured_value(self) -> None:
        """Validate async api_version property returns configured value when set."""
        client, _, _ = _make_async_client()
        client.set_configured_api_version("62.0")

        assert client.api_version == "62.0"

    def test_async_api_version_property_uses_cached_value(self) -> None:
        """Validate async api_version property returns cached value when present."""
        client, _, _ = _make_async_client()
        client.set_resolved_api_version("63.0")

        assert client.api_version == "63.0"

    def test_async_api_version_property_defaults_when_unset(self) -> None:
        """Validate async api_version property falls back to default value."""
        client, _, _ = _make_async_client()

        assert client.api_version == DEFAULT_API_VERSION

    async def test_get_api_version_returns_configured_value(self) -> None:
        """Validate async version lookup returns configured value without request."""
        client, _, transport = _make_async_client(content=_json_bytes([]))
        client.set_configured_api_version("62.0")

        assert await client.get_api_version() == "62.0"
        assert transport.send.call_count == 0

    async def test_get_api_version_falls_back_on_invalid_discovery_payload(
        self,
    ) -> None:
        """Validate async fallback to default when discovery payload is invalid."""
        client, _, _ = _make_async_client(content=_json_bytes({"unexpected": "shape"}))

        assert await client.get_api_version() == DEFAULT_API_VERSION

    async def test_get_api_version_falls_back_when_latest_has_no_version(self) -> None:
        """Validate async fallback when latest version item lacks version value."""
        payload = _json_bytes([{"label": "vLatest", "url": "/services/data/v99.0"}])
        client, _, _ = _make_async_client(content=payload)

        assert await client.get_api_version() == DEFAULT_API_VERSION


# ---------------------------------------------------------------------------
# Error-mapping integration — sync
# ---------------------------------------------------------------------------


def _sf_body(code: str, message: str = "msg") -> bytes:
    """Handle sf body."""
    return _json_bytes([{"errorCode": code, "message": message, "fields": []}])


class TestSalesforceAPIClientErrorMapping:
    """Verify sync client raises typed SF errors over generic HTTP errors."""

    def test_validation_error_on_required_field_missing(self) -> None:
        """Validate validation error on required field missing."""
        client, _, _ = _make_client(
            status_code=400, content=_sf_body("REQUIRED_FIELD_MISSING")
        )
        with pytest.raises(SalesforceValidationError) as exc_info:
            client.get(SERVICE_PATH)
        assert exc_info.value.status_code == 400
        assert exc_info.value.errors[0].error_code == "REQUIRED_FIELD_MISSING"

    def test_duplicate_error_on_duplicate_value(self) -> None:
        """Validate duplicate error on duplicate value."""
        client, _, _ = _make_client(
            status_code=400, content=_sf_body("DUPLICATE_VALUE")
        )
        with pytest.raises(SalesforceDuplicateError):
            client.get(SERVICE_PATH)

    def test_base_salesforce_error_for_unknown_code(self) -> None:
        """Validate base salesforce error for unknown code."""
        client, _, _ = _make_client(
            status_code=400, content=_sf_body("SOME_EXOTIC_CODE")
        )
        with pytest.raises(SalesforceAPIError) as exc_info:
            client.get(SERVICE_PATH)
        assert type(exc_info.value) is SalesforceAPIError

    def test_falls_back_to_http_error_on_non_sf_body(self) -> None:
        """A plain 401 with non-Salesforce body raises UnauthorizedError."""
        client, _, _ = _make_client(status_code=401, content=b"Unauthorized")
        with pytest.raises(UnauthorizedError):
            client.get(SERVICE_PATH)

    def test_salesforce_error_is_superclass_of_validation_error(self) -> None:
        """Validate salesforce error is superclass of validation error."""
        client, _, _ = _make_client(
            status_code=400, content=_sf_body("REQUIRED_FIELD_MISSING")
        )
        with pytest.raises(SalesforceAPIError):
            client.get(SERVICE_PATH)

    def test_http_error_url_contains_instance_url(self) -> None:
        """Error URL must reflect instance_url, not the empty base_url."""
        client, _, _ = _make_client(status_code=404, content=b"Not Found")
        with pytest.raises(NotFoundError) as exc_info:
            client.get(SERVICE_PATH)
        assert exc_info.value.url.startswith(INSTANCE_URL)


# ---------------------------------------------------------------------------
# Error-mapping integration — async
# ---------------------------------------------------------------------------


class TestAsyncSalesforceAPIClientErrorMapping:
    """Verify async client raises typed SF errors over generic HTTP errors."""

    async def test_validation_error_on_required_field_missing(self) -> None:
        """Validate validation error on required field missing."""
        client, _, _ = _make_async_client(
            status_code=400, content=_sf_body("REQUIRED_FIELD_MISSING")
        )
        with pytest.raises(SalesforceValidationError) as exc_info:
            await client.get(SERVICE_PATH)
        assert exc_info.value.status_code == 400
        assert exc_info.value.errors[0].error_code == "REQUIRED_FIELD_MISSING"

    async def test_duplicate_error_on_duplicate_value(self) -> None:
        """Validate duplicate error on duplicate value."""
        client, _, _ = _make_async_client(
            status_code=400, content=_sf_body("DUPLICATE_VALUE")
        )
        with pytest.raises(SalesforceDuplicateError):
            await client.get(SERVICE_PATH)

    async def test_base_salesforce_error_for_unknown_code(self) -> None:
        """Validate base salesforce error for unknown code."""
        client, _, _ = _make_async_client(
            status_code=400, content=_sf_body("SOME_EXOTIC_CODE")
        )
        with pytest.raises(SalesforceAPIError) as exc_info:
            await client.get(SERVICE_PATH)
        assert type(exc_info.value) is SalesforceAPIError

    async def test_falls_back_to_http_error_on_non_sf_body(self) -> None:
        """A plain 401 with non-Salesforce body raises UnauthorizedError."""
        client, _, _ = _make_async_client(status_code=401, content=b"Unauthorized")
        with pytest.raises(UnauthorizedError):
            await client.get(SERVICE_PATH)

    async def test_salesforce_error_is_superclass_of_validation_error(self) -> None:
        """Validate salesforce error is superclass of validation error."""
        client, _, _ = _make_async_client(
            status_code=400, content=_sf_body("REQUIRED_FIELD_MISSING")
        )
        with pytest.raises(SalesforceAPIError):
            await client.get(SERVICE_PATH)
