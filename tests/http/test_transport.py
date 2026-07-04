"""Tests for HttpxSyncTransport and HttpxAsyncTransport."""

# pyright: reportPrivateUsage=false
# pylint: disable=protected-access,too-many-lines

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from typing import Any

import httpx2 as httpx
import pytest

import plynth.http.transport as transport_module
from plynth.base.middleware import (
    AsyncMiddleware,
    NextAsyncHandler,
    NextSyncHandler,
    SyncMiddleware,
)
from plynth.base.request import Request
from plynth.base.response import AsyncStreamingResponse, Response, StreamingResponse
from plynth.base.transport import BaseAsyncTransport, BaseSyncTransport
from plynth.cache import DummyCache, DummyCacheConfig, LocMemCache, LocMemCacheConfig
from plynth.http.auth import (
    BasicAuthConfig,
    BearerAuthConfig,
    OAuth2ClientCredentialsConfig,
)
from plynth.http.middleware.auth import (
    AsyncBasicAuthMiddleware,
    AsyncBearerTokenAuthMiddleware,
    AsyncOAuth2ClientCredentialsMiddleware,
    BasicAuthMiddleware,
    BearerTokenAuthMiddleware,
    OAuth2AuthMiddleware,
)
from plynth.http.policies import HttpRetryPolicy
from plynth.http.response import HttpResponse
from plynth.http.settings import HTTPSettings
from plynth.http.transport import HttpxAsyncTransport, HttpxSyncTransport, scrub_headers
from plynth.middleware.cache import AsyncCacheMiddleware, CacheMiddleware
from plynth.middleware.retry import AsyncRetryMiddleware, RetryMiddleware
from tests.http.conftest import (
    DUMMY_BASIC_PASSWORD,
    DUMMY_BASIC_USERNAME,
    DUMMY_BEARER_TOKEN,
    DUMMY_CLIENT_ID,
    DUMMY_CLIENT_SECRET,
    DUMMY_TOKEN_URL,
)

# ---------------------------------------------------------------------------
# Typed-settings helpers for auth (ADR-0011)
# ---------------------------------------------------------------------------


class _BearerSettings(HTTPSettings):
    """Settings stub that wires bearer token auth via the typed auth property."""

    @property
    def auth(self) -> BearerAuthConfig:
        """Return auth."""
        return BearerAuthConfig(token=DUMMY_BEARER_TOKEN)


class _BasicSettings(HTTPSettings):
    """Settings stub that wires HTTP Basic auth via the typed auth property."""

    @property
    def auth(self) -> BasicAuthConfig:
        """Return auth."""
        return BasicAuthConfig(
            username=DUMMY_BASIC_USERNAME, password=DUMMY_BASIC_PASSWORD
        )


class _OAuth2Settings(HTTPSettings):
    """Settings stub that wires OAuth2 CC auth via the typed auth property."""

    @property
    def auth(self) -> OAuth2ClientCredentialsConfig:
        """Return auth."""
        return OAuth2ClientCredentialsConfig(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
        )


def _make_sync_client(handler: httpx.MockTransport) -> httpx.Client:
    """Create an httpx2.Client with a mock transport for testing."""
    return httpx.Client(transport=handler)


def _make_async_client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    """Create an httpx2.AsyncClient with a mock transport for testing."""
    return httpx.AsyncClient(transport=handler)


def _mock_response(
    status_code: int = 200,
    body: bytes = b"{}",
    headers: dict[str, str] | None = None,
) -> httpx.MockTransport:
    """Return an httpx2.MockTransport that always returns the given response."""
    response_headers = dict(headers or {})

    def handler(_request: httpx.Request) -> httpx.Response:
        """Return handler."""
        return httpx.Response(
            status_code=status_code,
            content=body,
            headers=response_headers,
        )

    return httpx.MockTransport(handler)


class TestHttpxSyncTransport:
    """Tests for HttpxSyncTransport."""

    def test_send_returns_response(self) -> None:
        """A successful GET returns a Response with the correct status and body."""
        body = json.dumps({"ok": True}).encode()
        client = _make_sync_client(_mock_response(200, body))
        transport = HttpxSyncTransport(client=client)

        resp = transport.send(Request(method="GET", url="https://example.com"))

        assert isinstance(resp, Response)
        assert resp.status_code == 200
        assert json.loads(resp.content) == {"ok": True}
        assert isinstance(resp, HttpResponse)
        assert isinstance(getattr(resp, "_raw", None), httpx.Response)

    def test_send_passes_method_and_url(self) -> None:
        """The method and URL are forwarded to httpx2 correctly."""
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Return handler."""
            seen["method"] = request.method
            seen["url"] = str(request.url)
            return httpx.Response(200, content=b"")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        transport = HttpxSyncTransport(client=client)
        transport.send(Request(method="POST", url="https://api.example.com/items"))

        assert seen["method"] == "POST"
        assert "api.example.com" in seen["url"]

    def test_send_passes_headers(self) -> None:
        """Custom headers are forwarded to httpx2."""
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Return handler."""
            seen.update(dict(request.headers))
            return httpx.Response(200, content=b"")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        transport = HttpxSyncTransport(client=client)
        transport.send(
            Request(
                method="GET",
                url="https://example.com",
                headers={"Authorization": "Bearer token"},
            )
        )

        assert seen.get("authorization") == "Bearer token"

    def test_send_passes_content(self) -> None:
        """Request body (content) is forwarded to httpx2."""
        seen: dict[str, bytes] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Return handler."""
            seen["body"] = request.content
            return httpx.Response(200, content=b"")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        transport = HttpxSyncTransport(client=client)
        transport.send(
            Request(method="POST", url="https://example.com", content=b'{"x": 1}')
        )

        assert seen["body"] == b'{"x": 1}'

    def test_send_non_200_status(self) -> None:
        """Non-200 status codes are returned as-is, without raising."""
        client = _make_sync_client(_mock_response(404, b"not found"))
        transport = HttpxSyncTransport(client=client)

        resp = transport.send(Request(method="GET", url="https://example.com"))

        assert resp.status_code == 404

    def test_response_headers_mapped(self) -> None:
        """Response headers from httpx2 are mapped to the Response object."""
        client = _make_sync_client(
            _mock_response(200, b"", headers={"X-Custom": "value"})
        )
        transport = HttpxSyncTransport(client=client)

        resp = transport.send(Request(method="GET", url="https://example.com"))

        assert resp.headers.get("x-custom") == "value"

    def test_context_manager(self) -> None:
        """HttpxSyncTransport works as a context manager."""
        client = _make_sync_client(_mock_response(200, b""))
        with HttpxSyncTransport(client=client) as transport:
            resp = transport.send(Request(method="GET", url="https://example.com"))
        assert resp.status_code == 200

    def test_default_client_created_when_none_passed(self) -> None:
        """HttpxSyncTransport creates its own client if none is provided."""
        transport = HttpxSyncTransport()
        assert transport._client is not None
        transport.close()

    def test_per_request_timeout_overrides_transport_timeout(self) -> None:
        """When Request.timeout is set it is forwarded to httpx2 as a timeout kwarg."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Return handler."""
            seen["timeout"] = request.extensions.get("timeout")
            return httpx.Response(200, content=b"")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        transport = HttpxSyncTransport(client=client)
        transport.send(Request(method="GET", url="https://example.com", timeout=120.0))

        # httpx2 converts the float to a Timeout mapping in extensions
        assert seen["timeout"] is not None

    def test_no_per_request_timeout_uses_client_default(self) -> None:
        """When Request.timeout is None the transport timeout is not overridden."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Return handler."""
            seen["timeout"] = request.extensions.get("timeout")
            return httpx.Response(200, content=b"")

        client = httpx.Client(
            transport=httpx.MockTransport(handler),
            timeout=httpx.Timeout(5.0),
        )
        transport = HttpxSyncTransport(client=client)
        transport.send(Request(method="GET", url="https://example.com"))

        # transport-level timeout is still applied by httpx2 itself
        assert seen["timeout"] is not None

    def test_stream_request_returns_streaming_response(self) -> None:
        """A stream request returns StreamingResponse with unbuffered content."""
        body = b"chunk-1\nchunk-2\n"
        client = _make_sync_client(_mock_response(200, body))
        transport = HttpxSyncTransport(client=client)

        response = transport.send(
            Request(method="GET", url="https://example.com", stream=True)
        )

        assert isinstance(response, StreamingResponse)
        assert response.content == b""
        assert b"".join(response.iter_bytes()) == body
        response.close()

    def test_stream_request_forwards_timeout(self) -> None:
        """A stream request forwards per-request timeout to httpx2.send()."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture timeout extension for stream send path."""
            seen["timeout"] = request.extensions.get("timeout")
            return httpx.Response(200, content=b"stream")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        transport = HttpxSyncTransport(client=client)

        response = transport.send(
            Request(
                method="GET",
                url="https://example.com",
                stream=True,
                timeout=45.0,
            )
        )

        assert seen["timeout"] is not None
        assert isinstance(response, StreamingResponse)
        response.close()


class TestHttpxAsyncTransport:
    """Tests for HttpxAsyncTransport."""

    async def test_send_returns_response(self) -> None:
        """A successful GET returns a Response with the correct status and body."""
        body = json.dumps({"ok": True}).encode()
        client = _make_async_client(_mock_response(200, body))
        transport = HttpxAsyncTransport(client=client)

        resp = await transport.send(Request(method="GET", url="https://example.com"))

        assert isinstance(resp, Response)
        assert resp.status_code == 200
        assert json.loads(resp.content) == {"ok": True}
        assert isinstance(resp, HttpResponse)
        assert isinstance(getattr(resp, "_raw", None), httpx.Response)

    async def test_send_passes_method_and_url(self) -> None:
        """The method and URL are forwarded to httpx2 correctly."""
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Return handler."""
            seen["method"] = request.method
            seen["url"] = str(request.url)
            return httpx.Response(200, content=b"")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        transport = HttpxAsyncTransport(client=client)
        await transport.send(Request(method="DELETE", url="https://api.example.com/1"))

        assert seen["method"] == "DELETE"
        assert "api.example.com" in seen["url"]

    async def test_send_passes_headers(self) -> None:
        """Custom headers are forwarded to httpx2."""
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Return handler."""
            seen.update(dict(request.headers))
            return httpx.Response(200, content=b"")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        transport = HttpxAsyncTransport(client=client)
        await transport.send(
            Request(
                method="GET",
                url="https://example.com",
                headers={"X-Api-Key": "secret"},
            )
        )

        assert seen.get("x-api-key") == "secret"

    async def test_send_passes_content(self) -> None:
        """Request body (content) is forwarded to httpx2."""
        seen: dict[str, bytes] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Return handler."""
            seen["body"] = request.content
            return httpx.Response(200, content=b"")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        transport = HttpxAsyncTransport(client=client)
        await transport.send(
            Request(method="POST", url="https://example.com", content=b'{"y": 2}')
        )

        assert seen["body"] == b'{"y": 2}'

    async def test_send_non_200_status(self) -> None:
        """Non-200 status codes are returned as-is, without raising."""
        client = _make_async_client(_mock_response(503, b"unavailable"))
        transport = HttpxAsyncTransport(client=client)

        resp = await transport.send(Request(method="GET", url="https://example.com"))

        assert resp.status_code == 503

    async def test_response_headers_mapped(self) -> None:
        """Response headers from httpx2 are mapped to the Response object."""
        client = _make_async_client(
            _mock_response(200, b"", headers={"X-Rate-Limit": "100"})
        )
        transport = HttpxAsyncTransport(client=client)

        resp = await transport.send(Request(method="GET", url="https://example.com"))

        assert resp.headers.get("x-rate-limit") == "100"

    async def test_async_context_manager(self) -> None:
        """HttpxAsyncTransport works as an async context manager."""
        client = _make_async_client(_mock_response(201, b""))
        async with HttpxAsyncTransport(client=client) as transport:
            resp = await transport.send(
                Request(method="POST", url="https://example.com")
            )
        assert resp.status_code == 201

    async def test_default_client_created_when_none_passed(self) -> None:
        """HttpxAsyncTransport creates its own client if none is provided."""
        transport = HttpxAsyncTransport()
        assert transport._client is not None
        await transport.aclose()

    async def test_per_request_timeout_overrides_transport_timeout(self) -> None:
        """When Request.timeout is set it is forwarded to httpx2 as a timeout kwarg."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Return handler."""
            seen["timeout"] = request.extensions.get("timeout")
            return httpx.Response(200, content=b"")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        transport = HttpxAsyncTransport(client=client)
        await transport.send(
            Request(method="GET", url="https://example.com", timeout=120.0)
        )

        assert seen["timeout"] is not None

    async def test_stream_request_returns_async_streaming_response(self) -> None:
        """A stream request returns AsyncStreamingResponse with unbuffered content."""
        body = b"chunk-1\nchunk-2\n"
        client = _make_async_client(_mock_response(200, body))
        transport = HttpxAsyncTransport(client=client)

        response = await transport.send(
            Request(method="GET", url="https://example.com", stream=True)
        )

        assert isinstance(response, AsyncStreamingResponse)
        assert response.content == b""
        chunks = [chunk async for chunk in response.aiter_bytes()]
        assert b"".join(chunks) == body
        await response.aclose()

    async def test_stream_request_forwards_timeout(self) -> None:
        """An async stream request forwards timeout to httpx2.send()."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture timeout extension for async stream send path."""
            seen["timeout"] = request.extensions.get("timeout")
            return httpx.Response(200, content=b"stream")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        transport = HttpxAsyncTransport(client=client)

        response = await transport.send(
            Request(
                method="GET",
                url="https://example.com",
                stream=True,
                timeout=45.0,
            )
        )

        assert seen["timeout"] is not None
        assert isinstance(response, AsyncStreamingResponse)
        await response.aclose()


class TestHttpxSyncTransportStatusCodes:
    """Test suite for HttpxSyncTransportStatusCodes."""

    @pytest.mark.parametrize("status_code", [200, 201, 400, 404, 500, 503])
    def test_sync_transport_all_status_codes(self, status_code: int) -> None:
        """HttpxSyncTransport preserves any HTTP status code."""
        client = _make_sync_client(_mock_response(status_code, b""))
        transport = HttpxSyncTransport(client=client)
        resp = transport.send(Request(method="GET", url="https://example.com"))
        assert resp.status_code == status_code


class TestHttpxAsyncTransportStatusCodes:
    """Test suite for HttpxAsyncTransportStatusCodes."""

    @pytest.mark.parametrize("status_code", [200, 201, 400, 404, 500, 503])
    async def test_async_transport_all_status_codes(self, status_code: int) -> None:
        """HttpxAsyncTransport preserves any HTTP status code."""
        client = _make_async_client(_mock_response(status_code, b""))
        transport = HttpxAsyncTransport(client=client)
        resp = await transport.send(Request(method="GET", url="https://example.com"))
        assert resp.status_code == status_code


class TestHttpxTransportFromSettings:
    """Tests for HttpxSyncTransport.from_settings() and
    HttpxAsyncTransport.from_settings()."""

    def test_from_settings_returns_sync_transport(self) -> None:
        """Validate from settings returns sync transport."""
        s = HTTPSettings()
        transport = HttpxSyncTransport.from_settings(s)
        assert isinstance(transport, HttpxSyncTransport)
        transport.close()

    def test_from_settings_wires_retry_middleware(self) -> None:
        """Validate from settings wires retry middleware."""
        s = HTTPSettings(max_attempts=5)
        transport = HttpxSyncTransport.from_settings(s)
        retry_mw = transport._middlewares[-1]
        assert isinstance(retry_mw, RetryMiddleware)
        assert isinstance(retry_mw._policy, HttpRetryPolicy)
        assert retry_mw._policy.max_attempts == 5
        transport.close()

    def test_from_settings_no_auth_by_default(self) -> None:
        """Validate from settings no auth by default."""
        s = HTTPSettings()
        transport = HttpxSyncTransport.from_settings(s)
        assert len(transport._middlewares) == 1
        assert isinstance(transport._middlewares[0], RetryMiddleware)
        transport.close()

    def test_from_settings_bearer_token(self) -> None:
        """Validate from settings bearer token."""
        transport = HttpxSyncTransport.from_settings(_BearerSettings())
        assert isinstance(transport._middlewares[0], BearerTokenAuthMiddleware)
        transport.close()

    def test_from_settings_oauth2(self) -> None:
        """Validate from settings oauth2."""
        transport = HttpxSyncTransport.from_settings(_OAuth2Settings())
        assert isinstance(transport._middlewares[0], OAuth2AuthMiddleware)
        transport.close()

    def test_from_settings_basic_auth(self) -> None:
        """Validate from settings basic auth."""
        transport = HttpxSyncTransport.from_settings(_BasicSettings())
        assert isinstance(transport._middlewares[0], BasicAuthMiddleware)
        transport.close()

    async def test_from_settings_returns_async_transport(self) -> None:
        """Validate from settings returns async transport."""
        s = HTTPSettings()
        transport = HttpxAsyncTransport.from_settings(s)
        assert isinstance(transport, HttpxAsyncTransport)
        await transport.aclose()

    async def test_from_settings_async_wires_retry_middleware(self) -> None:
        """Validate from settings async wires retry middleware."""
        s = HTTPSettings(max_attempts=4)
        transport = HttpxAsyncTransport.from_settings(s)
        retry_mw = transport._middlewares[-1]
        assert isinstance(retry_mw, AsyncRetryMiddleware)
        assert retry_mw._policy.max_attempts == 4
        await transport.aclose()

    def test_from_settings_uses_typed_retry_policy(self) -> None:
        """settings.retry takes precedence over max_attempts when set."""

        class _CustomRetrySettings(HTTPSettings):
            """Represent CustomRetrySettings."""

            @property
            def retry(self) -> HttpRetryPolicy:
                """Return retry."""
                return HttpRetryPolicy(
                    max_attempts=7,
                    backoff_initial=2.0,
                    retryable_status_codes=frozenset({429, 503}),
                )

        transport = HttpxSyncTransport.from_settings(_CustomRetrySettings())
        retry_mw = transport._middlewares[-1]
        assert isinstance(retry_mw, RetryMiddleware)
        assert retry_mw._policy.max_attempts == 7
        assert retry_mw._policy.backoff_initial == 2.0
        assert retry_mw._policy.retryable_status_codes == frozenset({429, 503})
        transport.close()

    async def test_from_settings_async_uses_typed_retry_policy(self) -> None:
        """Async: settings.retry takes precedence over max_attempts when set."""

        class _CustomRetrySettings(HTTPSettings):
            """Represent CustomRetrySettings."""

            @property
            def retry(self) -> HttpRetryPolicy:
                """Return retry."""
                return HttpRetryPolicy(
                    max_attempts=6,
                    backoff_max=5.0,
                )

        transport = HttpxAsyncTransport.from_settings(_CustomRetrySettings())
        retry_mw = transport._middlewares[-1]
        assert isinstance(retry_mw, AsyncRetryMiddleware)
        assert retry_mw._policy.max_attempts == 6
        assert retry_mw._policy.backoff_max == 5.0
        await transport.aclose()

    def test_build_sync_client_honors_httpx2_options(self) -> None:
        """Client builder wires http2, trust_env, redirects, and limits."""
        captured: dict[str, object] = {}
        real_client = httpx.Client
        httpx_mod: Any = httpx

        class _DummyClient:
            def close(self) -> None:
                return

        def _fake_client(**kwargs: object) -> _DummyClient:
            captured.update(kwargs)
            return _DummyClient()

        httpx_mod.Client = _fake_client
        try:
            settings = HTTPSettings(
                http2=True,
                trust_env=False,
                max_redirects=9,
                max_connections=40,
                max_keepalive_connections=12,
                keepalive_expiry=25.0,
            )
            client = transport_module._build_httpx_client(settings)
            assert isinstance(client, _DummyClient)
            assert captured["http2"] is True
            assert captured["trust_env"] is False
            assert captured["max_redirects"] == 9
            limits = captured["limits"]
            assert isinstance(limits, httpx.Limits)
        finally:
            httpx_mod.Client = real_client

    def test_build_sync_client_omits_limits_when_not_set(self) -> None:
        """Client builder omits limits kwarg when all limit settings are None."""
        captured: dict[str, object] = {}
        real_client = httpx.Client
        httpx_mod: Any = httpx

        class _DummyClient:
            def close(self) -> None:
                return

        def _fake_client(**kwargs: object) -> _DummyClient:
            captured.update(kwargs)
            return _DummyClient()

        httpx_mod.Client = _fake_client
        try:
            settings = HTTPSettings(
                max_connections=None,
                max_keepalive_connections=None,
                keepalive_expiry=None,
            )
            client = transport_module._build_httpx_client(settings)
            assert isinstance(client, _DummyClient)
            assert "limits" not in captured
        finally:
            httpx_mod.Client = real_client

    async def test_build_async_client_honors_httpx2_options(self) -> None:
        """Async client builder wires http2, trust_env, redirects, and limits."""
        captured: dict[str, object] = {}
        real_async_client = httpx.AsyncClient
        httpx_mod: Any = httpx

        class _DummyAsyncClient:
            async def aclose(self) -> None:  # C0116
                return

        def _fake_async_client(**kwargs: object) -> _DummyAsyncClient:
            captured.update(kwargs)
            return _DummyAsyncClient()

        httpx_mod.AsyncClient = _fake_async_client
        try:
            settings = HTTPSettings(
                http2=True,
                trust_env=False,
                max_redirects=7,
                max_connections=30,
                max_keepalive_connections=10,
                keepalive_expiry=20.0,
            )
            client = transport_module._build_httpx_async_client(settings)
            assert isinstance(client, _DummyAsyncClient)
            assert captured["http2"] is True
            assert captured["trust_env"] is False
            assert captured["max_redirects"] == 7
            limits = captured["limits"]
            assert isinstance(limits, httpx.Limits)
            await client.aclose()
        finally:
            httpx_mod.AsyncClient = real_async_client

    async def test_build_async_client_omits_limits_when_not_set(self) -> None:
        """Async builder omits limits kwarg when all limit settings are None."""
        captured: dict[str, object] = {}
        real_async_client = httpx.AsyncClient
        httpx_mod: Any = httpx

        class _DummyAsyncClient:
            async def aclose(self) -> None:
                return

        def _fake_async_client(**kwargs: object) -> _DummyAsyncClient:
            captured.update(kwargs)
            return _DummyAsyncClient()

        httpx_mod.AsyncClient = _fake_async_client
        try:
            settings = HTTPSettings(
                max_connections=None,
                max_keepalive_connections=None,
                keepalive_expiry=None,
            )
            client = transport_module._build_httpx_async_client(settings)
            assert isinstance(client, _DummyAsyncClient)
            assert "limits" not in captured
            await client.aclose()
        finally:
            httpx_mod.AsyncClient = real_async_client

    def test_inherits_base_sync_transport(self) -> None:
        """Validate inherits base sync transport."""
        transport = HttpxSyncTransport()
        assert isinstance(transport, BaseSyncTransport)
        transport.close()

    async def test_inherits_base_async_transport(self) -> None:
        """Validate inherits base async transport."""
        transport = HttpxAsyncTransport()
        assert isinstance(transport, BaseAsyncTransport)
        await transport.aclose()


class TestHttpxAsyncTransportFromSettingsAuth:
    """Tests for auth middleware wiring in HttpxAsyncTransport.from_settings()."""

    async def test_no_auth_by_default(self) -> None:
        """Validate no auth by default."""
        transport = HttpxAsyncTransport.from_settings(HTTPSettings())
        assert len(transport._middlewares) == 1
        assert isinstance(transport._middlewares[0], AsyncRetryMiddleware)
        await transport.aclose()

    async def test_bearer_token_wired(self) -> None:
        """Validate bearer token wired."""
        transport = HttpxAsyncTransport.from_settings(_BearerSettings())
        assert isinstance(transport._middlewares[0], AsyncBearerTokenAuthMiddleware)
        await transport.aclose()

    async def test_bearer_token_produces_correct_header(self) -> None:
        """Validate bearer token produces correct header."""
        transport = HttpxAsyncTransport.from_settings(_BearerSettings())
        req = Request(method="GET", url="https://example.com")
        mw = transport._middlewares[0]
        assert isinstance(mw, AsyncBearerTokenAuthMiddleware)

        async def _next(_r: Request) -> Response:
            """Handle next."""
            return Response(status_code=200, content=b"")

        await mw.handle(req, _next)
        assert req.headers.get("Authorization") == f"Bearer {DUMMY_BEARER_TOKEN}"
        await transport.aclose()

    async def test_basic_auth_wired(self) -> None:
        """Validate basic auth wired."""
        transport = HttpxAsyncTransport.from_settings(_BasicSettings())
        assert isinstance(transport._middlewares[0], AsyncBasicAuthMiddleware)
        await transport.aclose()

    async def test_basic_auth_produces_correct_header(self) -> None:
        """Validate basic auth produces correct header."""

        transport = HttpxAsyncTransport.from_settings(_BasicSettings())
        req = Request(method="GET", url="https://example.com")
        mw = transport._middlewares[0]
        assert isinstance(mw, AsyncBasicAuthMiddleware)

        async def _next(_r: Request) -> Response:
            """Handle next."""
            return Response(status_code=200, content=b"")

        await mw.handle(req, _next)
        expected = base64.b64encode(
            f"{DUMMY_BASIC_USERNAME}:{DUMMY_BASIC_PASSWORD}".encode()
        ).decode()
        assert req.headers.get("Authorization") == f"Basic {expected}"
        await transport.aclose()


class TestHttpxTransportFromSettingsCache:
    """Tests for cache middleware wiring via the typed CacheConfig API (ADR-0010)."""

    def _make_settings_with_cache(self, cache_name: str = "responses") -> HTTPSettings:
        """Handle make settings with cache."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def caches(self) -> dict[str, Any]:
                """Return caches."""
                return {cache_name: LocMemCacheConfig()}

            @property
            def default_cache(self) -> str:
                """Return default cache."""
                return cache_name

        return _Settings()

    def test_no_cache_middleware_by_default(self) -> None:
        """No CacheMiddleware is added when caches returns None."""
        s = HTTPSettings()
        transport = HttpxSyncTransport.from_settings(s)
        cache_mws = [
            m for m in transport._middlewares if isinstance(m, CacheMiddleware)
        ]
        assert cache_mws == []
        transport.close()

    def test_cache_middleware_added_when_caches_configured(self) -> None:
        """CacheMiddleware is prepended when caches and default_cache are set."""
        s = self._make_settings_with_cache()
        transport = HttpxSyncTransport.from_settings(s)
        assert isinstance(transport._middlewares[0], CacheMiddleware)
        transport.close()

    def test_no_cache_when_default_cache_not_in_caches(self) -> None:
        """No cache is wired when default_cache references a missing key."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def caches(self) -> dict[str, Any]:
                """Return caches."""
                return {"responses": LocMemCacheConfig()}

            @property
            def default_cache(self) -> str:
                """Return default cache."""
                return "missing_key"

        transport = HttpxSyncTransport.from_settings(_Settings())
        cache_mws = [
            m for m in transport._middlewares if isinstance(m, CacheMiddleware)
        ]
        assert cache_mws == []
        transport.close()

    def test_no_cache_when_caches_is_none_but_default_cache_set(self) -> None:
        """No cache is wired when caches is None, even if default_cache is set."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def default_cache(self) -> str:
                """Return default cache."""
                return "responses"

        transport = HttpxSyncTransport.from_settings(_Settings())
        cache_mws = [
            m for m in transport._middlewares if isinstance(m, CacheMiddleware)
        ]
        assert cache_mws == []
        transport.close()

    async def test_async_cache_middleware_added_when_caches_configured(self) -> None:
        """AsyncCacheMiddleware is prepended when caches and default_cache are set."""
        s = self._make_settings_with_cache()
        transport = HttpxAsyncTransport.from_settings(s)
        assert isinstance(transport._middlewares[0], AsyncCacheMiddleware)
        await transport.aclose()

    async def test_async_no_cache_middleware_by_default(self) -> None:
        """No AsyncCacheMiddleware is added when caches returns None."""
        transport = HttpxAsyncTransport.from_settings(HTTPSettings())
        cache_mws = [
            m for m in transport._middlewares if isinstance(m, AsyncCacheMiddleware)
        ]
        assert cache_mws == []
        await transport.aclose()

    def test_dummy_cache_config_wires_dummy_cache(self) -> None:
        """DummyCacheConfig produces a DummyCache backend in CacheMiddleware."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def caches(self) -> dict[str, Any]:
                """Return caches."""
                return {"responses": DummyCacheConfig()}

            @property
            def default_cache(self) -> str:
                """Return default cache."""
                return "responses"

        transport = HttpxSyncTransport.from_settings(_Settings())
        mw = transport._middlewares[0]
        assert isinstance(mw, CacheMiddleware)
        assert isinstance(mw._backend, DummyCache)
        transport.close()


class TestHttpxTransportMiddlewaresParam:
    """Tests that middlewares can be passed to httpx2 transport constructors."""

    def test_sync_transport_stores_middlewares(self) -> None:
        """Validate sync transport stores middlewares."""

        class _Noop:
            """Represent Noop."""

            def handle(
                self, request: Request, next_handler: NextSyncHandler
            ) -> Response:
                """Return handle."""
                return next_handler(request)

        mw = _Noop()
        assert isinstance(mw, SyncMiddleware)
        transport = HttpxSyncTransport(middlewares=[mw])
        assert mw in transport._middlewares
        transport.close()

    async def test_async_transport_stores_middlewares(self) -> None:
        """Validate async transport stores middlewares."""

        class _AsyncNoop:
            """Represent AsyncNoop."""

            async def handle(
                self, request: Request, next_handler: NextAsyncHandler
            ) -> Response:
                """Return handle."""
                return await next_handler(request)

        mw = _AsyncNoop()
        assert isinstance(mw, AsyncMiddleware)
        transport = HttpxAsyncTransport(middlewares=[mw])
        assert mw in transport._middlewares
        await transport.aclose()


# ---------------------------------------------------------------------------
# _scrub_headers
# ---------------------------------------------------------------------------


class TestScrubHeaders:
    """Tests for the scrub_headers helper (ADR-0014 § 4)."""

    _scrub: Callable[[dict[str, str]], dict[str, str]]

    def setup_method(self) -> None:
        """Return setup method."""

        self._scrub = scrub_headers

    def test_authorization_is_redacted(self) -> None:
        """Validate authorization is redacted."""
        result = self._scrub({"Authorization": "Bearer secret"})
        assert result["Authorization"] == "[REDACTED]"

    def test_cookie_is_redacted(self) -> None:
        """Validate cookie is redacted."""
        result = self._scrub({"Cookie": "session=abc"})
        assert result["Cookie"] == "[REDACTED]"

    def test_set_cookie_is_redacted(self) -> None:
        """Validate set cookie is redacted."""
        result = self._scrub({"Set-Cookie": "session=abc; HttpOnly"})
        assert result["Set-Cookie"] == "[REDACTED]"

    def test_x_api_key_is_redacted(self) -> None:
        """Validate x api key is redacted."""
        result = self._scrub({"X-Api-Key": "my-key"})
        assert result["X-Api-Key"] == "[REDACTED]"

    def test_proxy_authorization_is_redacted(self) -> None:
        """Validate proxy authorization is redacted."""
        result = self._scrub({"Proxy-Authorization": "Basic abc"})
        assert result["Proxy-Authorization"] == "[REDACTED]"

    def test_scrubbing_is_case_insensitive(self) -> None:
        """Validate scrubbing is case insensitive."""
        result = self._scrub({"authorization": "Bearer secret"})
        assert result["authorization"] == "[REDACTED]"

    def test_non_sensitive_headers_pass_through(self) -> None:
        """Validate non sensitive headers pass through."""
        headers = {"Content-Type": "application/json", "X-Request-Id": "123"}
        result = self._scrub(headers)
        assert result == headers

    def test_mixed_headers(self) -> None:
        """Validate mixed headers."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer secret",
            "X-Request-Id": "abc",
        }
        result = self._scrub(headers)
        assert result["Content-Type"] == "application/json"
        assert result["Authorization"] == "[REDACTED]"
        assert result["X-Request-Id"] == "abc"

    def test_original_dict_is_not_mutated(self) -> None:
        """Validate original dict is not mutated."""
        original = {"Authorization": "Bearer secret"}
        self._scrub(original)
        assert original["Authorization"] == "Bearer secret"

    def test_empty_dict_returns_empty(self) -> None:
        """Validate empty dict returns empty."""
        assert self._scrub({}) == {}


# ---------------------------------------------------------------------------
# log_bodies — sync transport
# ---------------------------------------------------------------------------


class TestSyncTransportLogBodies:
    """Tests for opt-in body logging in HttpxSyncTransport (ADR-0014 § 3)."""

    def test_log_bodies_false_by_default(self) -> None:
        """Validate log bodies false by default."""
        transport = HttpxSyncTransport()
        assert transport._log_bodies is False
        transport.close()

    def test_log_bodies_true_stored(self) -> None:
        """Validate log bodies true stored."""
        transport = HttpxSyncTransport(log_bodies=True)
        assert transport._log_bodies is True
        transport.close()

    def test_no_body_log_records_when_disabled(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate no body log records when disabled."""
        client = _make_sync_client(_mock_response(200, b'{"ok": true}'))
        transport = HttpxSyncTransport(client=client, log_bodies=False)

        with caplog.at_level("DEBUG", logger="plynth.http.transport"):
            transport.send(Request(method="GET", url="https://example.com"))

        body_records = [r for r in caplog.records if "body" in r.message.lower()]
        assert body_records == []

    def test_body_log_records_emitted_when_enabled(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate body log records emitted when enabled."""
        client = _make_sync_client(_mock_response(200, b'{"ok": true}'))
        transport = HttpxSyncTransport(client=client, log_bodies=True)

        with caplog.at_level("DEBUG", logger="plynth.http.transport"):
            transport.send(
                Request(method="POST", url="https://example.com", content=b"hello")
            )

        messages = [r.message for r in caplog.records]
        assert any("--> " in m and "body" in m for m in messages)
        assert any("<-- " in m and "body" in m for m in messages)

    def test_sensitive_headers_are_scrubbed_in_body_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate sensitive headers are scrubbed in body log."""
        client = _make_sync_client(_mock_response(200, b"{}"))
        transport = HttpxSyncTransport(client=client, log_bodies=True)

        with caplog.at_level("DEBUG", logger="plynth.http.transport"):
            transport.send(
                Request(
                    method="POST",
                    url="https://example.com",
                    headers={"Authorization": "Bearer supersecret"},
                    content=b"data",
                )
            )

        req_records = [
            r for r in caplog.records if "-->" in r.message and "body" in r.message
        ]
        assert req_records, "Expected a request body log record"
        assert "supersecret" not in req_records[0].message
        assert "[REDACTED]" in req_records[0].message

    def test_sensitive_query_values_are_scrubbed_in_logs(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate sensitive query values are scrubbed in sync logs."""
        client = _make_sync_client(_mock_response(200, b"{}"))
        transport = HttpxSyncTransport(client=client, log_bodies=True)

        with caplog.at_level("DEBUG", logger="plynth.http.transport"):
            transport.send(
                Request(
                    method="GET",
                    url="https://example.com?token=secret&keep=yes",
                )
            )

        messages = [r.message for r in caplog.records]
        assert any("token=%5BREDACTED%5D" in message for message in messages)
        assert all("token=secret" not in message for message in messages)

    def test_body_log_extra_field_set(self, caplog: pytest.LogCaptureFixture) -> None:
        """body_logging=True must appear as an extra field on body log records."""
        client = _make_sync_client(_mock_response(200, b"{}"))
        transport = HttpxSyncTransport(client=client, log_bodies=True)

        with caplog.at_level("DEBUG", logger="plynth.http.transport"):
            transport.send(Request(method="GET", url="https://example.com"))

        body_records = [r for r in caplog.records if getattr(r, "body_logging", False)]
        assert body_records, "Expected records with body_logging=True extra field"

    def test_original_request_not_mutated_by_body_log(self) -> None:
        """Scrubbing must not mutate the original Request headers."""
        client = _make_sync_client(_mock_response(200, b"{}"))
        transport = HttpxSyncTransport(client=client, log_bodies=True)
        request = Request(
            method="POST",
            url="https://example.com",
            headers={"Authorization": "Bearer secret"},
            content=b"data",
        )
        transport.send(request)
        assert request.headers["Authorization"] == "Bearer secret"


# ---------------------------------------------------------------------------
# log_bodies — async transport
# ---------------------------------------------------------------------------


class TestAsyncTransportLogBodies:
    """Tests for opt-in body logging in HttpxAsyncTransport (ADR-0014 § 3)."""

    async def test_log_bodies_false_by_default(self) -> None:
        """Validate log bodies false by default."""
        transport = HttpxAsyncTransport()
        assert transport._log_bodies is False
        await transport.aclose()

    async def test_log_bodies_true_stored(self) -> None:
        """Validate log bodies true stored."""
        transport = HttpxAsyncTransport(log_bodies=True)
        assert transport._log_bodies is True
        await transport.aclose()

    async def test_no_body_log_records_when_disabled(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate no body log records when disabled."""
        client = _make_async_client(_mock_response(200, b'{"ok": true}'))
        transport = HttpxAsyncTransport(client=client, log_bodies=False)

        with caplog.at_level("DEBUG", logger="plynth.http.transport"):
            await transport.send(Request(method="GET", url="https://example.com"))

        body_records = [r for r in caplog.records if "body" in r.message.lower()]
        assert body_records == []

    async def test_body_log_records_emitted_when_enabled(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate body log records emitted when enabled."""
        client = _make_async_client(_mock_response(200, b'{"ok": true}'))
        transport = HttpxAsyncTransport(client=client, log_bodies=True)

        with caplog.at_level("DEBUG", logger="plynth.http.transport"):
            await transport.send(
                Request(method="POST", url="https://example.com", content=b"hello")
            )

        messages = [r.message for r in caplog.records]
        assert any("--> " in m and "body" in m for m in messages)
        assert any("<-- " in m and "body" in m for m in messages)

    async def test_sensitive_headers_are_scrubbed_in_body_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate sensitive headers are scrubbed in body log."""
        client = _make_async_client(_mock_response(200, b"{}"))
        transport = HttpxAsyncTransport(client=client, log_bodies=True)

        with caplog.at_level("DEBUG", logger="plynth.http.transport"):
            await transport.send(
                Request(
                    method="POST",
                    url="https://example.com",
                    headers={"Authorization": "Bearer supersecret"},
                    content=b"data",
                )
            )

        req_records = [
            r for r in caplog.records if "-->" in r.message and "body" in r.message
        ]
        assert req_records, "Expected a request body log record"
        assert "supersecret" not in req_records[0].message
        assert "[REDACTED]" in req_records[0].message

    async def test_sensitive_query_values_are_scrubbed_in_logs(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate sensitive query values are scrubbed in async logs."""
        client = _make_async_client(_mock_response(200, b"{}"))
        transport = HttpxAsyncTransport(client=client, log_bodies=True)

        with caplog.at_level("DEBUG", logger="plynth.http.transport"):
            await transport.send(
                Request(
                    method="GET",
                    url="https://example.com?access_token=secret&keep=yes",
                )
            )

        messages = [r.message for r in caplog.records]
        assert any("access_token=%5BREDACTED%5D" in message for message in messages)
        assert all("access_token=secret" not in message for message in messages)

    async def test_original_request_not_mutated_by_body_log(self) -> None:
        """Scrubbing must not mutate the original Request headers."""
        client = _make_async_client(_mock_response(200, b"{}"))
        transport = HttpxAsyncTransport(client=client, log_bodies=True)
        request = Request(
            method="POST",
            url="https://example.com",
            headers={"Authorization": "Bearer secret"},
            content=b"data",
        )
        await transport.send(request)
        assert request.headers["Authorization"] == "Bearer secret"


class TestHttpxTransportCacheBackendSetting:
    """Tests for cache middleware wiring via from_settings() (ADR-0010)."""

    def _settings_with_locmem_cache(
        self,
        auth_config: Any = None,
        with_auth_cache: bool = False,
    ) -> HTTPSettings:
        """Return settings with a LocMemCache wired as the response cache."""
        _auth = auth_config

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def auth(self) -> Any:
                """Return auth."""
                return _auth

            @property
            def caches(self) -> dict[str, Any]:
                """Return caches."""
                cfg: dict[str, Any] = {"responses": LocMemCacheConfig()}
                if with_auth_cache:
                    cfg["tokens"] = LocMemCacheConfig()
                return cfg

            @property
            def default_cache(self) -> str:
                """Return default cache."""
                return "responses"

            @property
            def default_auth_cache(self) -> str | None:
                """Return default auth cache."""
                return "tokens" if with_auth_cache else None

        return _Settings()

    def _settings_with_dummy_cache(self, with_auth_cache: bool = False) -> HTTPSettings:
        """Return settings with a DummyCache wired as the response cache."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def caches(self) -> dict[str, Any]:
                """Return caches."""
                cfg: dict[str, Any] = {"responses": DummyCacheConfig()}
                if with_auth_cache:
                    cfg["tokens"] = DummyCacheConfig()
                return cfg

            @property
            def default_cache(self) -> str:
                """Return default cache."""
                return "responses"

            @property
            def default_auth_cache(self) -> str | None:
                """Return default auth cache."""
                return "tokens" if with_auth_cache else None

        return _Settings()

    def test_no_cache_middleware_by_default(self) -> None:
        """Validate no cache middleware by default."""
        transport = HttpxSyncTransport.from_settings(HTTPSettings())
        types = [type(m) for m in transport._middlewares]
        assert CacheMiddleware not in types
        transport.close()

    def test_cache_backend_adds_cache_middleware_first(self) -> None:
        """Validate cache backend adds cache middleware first."""
        s = self._settings_with_locmem_cache()
        transport = HttpxSyncTransport.from_settings(s)
        assert isinstance(transport._middlewares[0], CacheMiddleware)
        transport.close()

    def test_cache_backend_retry_still_last(self) -> None:
        """Validate cache backend retry still last."""
        s = self._settings_with_locmem_cache()
        transport = HttpxSyncTransport.from_settings(s)
        assert isinstance(transport._middlewares[-1], RetryMiddleware)
        transport.close()

    def test_auth_before_cache(self) -> None:
        """Auth middleware must precede cache to avoid cross-auth cache collisions."""
        s = self._settings_with_locmem_cache(
            auth_config=BearerAuthConfig(token=DUMMY_BEARER_TOKEN)
        )
        transport = HttpxSyncTransport.from_settings(s)
        assert isinstance(transport._middlewares[0], BearerTokenAuthMiddleware)
        assert isinstance(transport._middlewares[1], CacheMiddleware)
        assert isinstance(transport._middlewares[2], RetryMiddleware)
        transport.close()

    def test_dummy_cache_backend(self) -> None:
        """Validate dummy cache backend."""

        s = self._settings_with_dummy_cache()
        transport = HttpxSyncTransport.from_settings(s)
        mw = transport._middlewares[0]
        assert isinstance(mw, CacheMiddleware)
        assert isinstance(mw._backend, DummyCache)
        transport.close()

    def test_auth_cache_backend_sets_token_cache_on_oauth2(self) -> None:
        """default_auth_cache is passed as token_cache to the OAuth2 middleware."""

        class _FullSettings(HTTPSettings):
            """Represent FullSettings."""

            @property
            def auth(self) -> OAuth2ClientCredentialsConfig:
                """Return auth."""
                return OAuth2ClientCredentialsConfig(
                    client_id=DUMMY_CLIENT_ID,
                    client_secret=DUMMY_CLIENT_SECRET,
                    token_url=DUMMY_TOKEN_URL,
                )

            @property
            def caches(self) -> dict[str, Any]:
                """Return caches."""
                return {"tokens": DummyCacheConfig()}

            @property
            def default_auth_cache(self) -> str:
                """Return default auth cache."""
                return "tokens"

        transport = HttpxSyncTransport.from_settings(_FullSettings())
        mw = transport._middlewares[0]
        assert isinstance(mw, OAuth2AuthMiddleware)
        assert isinstance(mw._cache, DummyCache)
        transport.close()

    def test_auth_cache_backend_locmem(self) -> None:
        """Validate auth cache backend locmem."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def auth(self) -> OAuth2ClientCredentialsConfig:
                """Return auth."""
                return OAuth2ClientCredentialsConfig(
                    client_id=DUMMY_CLIENT_ID,
                    client_secret=DUMMY_CLIENT_SECRET,
                    token_url=DUMMY_TOKEN_URL,
                )

            @property
            def caches(self) -> dict[str, Any]:
                """Return caches."""
                return {"tokens": LocMemCacheConfig()}

            @property
            def default_auth_cache(self) -> str:
                """Return default auth cache."""
                return "tokens"

        transport = HttpxSyncTransport.from_settings(_Settings())
        mw = transport._middlewares[0]
        assert isinstance(mw, OAuth2AuthMiddleware)
        assert isinstance(mw._cache, LocMemCache)
        transport.close()

    def test_auth_cache_backend_ignored_for_bearer(self) -> None:
        """default_auth_cache has no effect when bearer token auth is used."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def auth(self) -> BearerAuthConfig:
                """Return auth."""
                return BearerAuthConfig(token=DUMMY_BEARER_TOKEN)

            @property
            def caches(self) -> dict[str, Any]:
                """Return caches."""
                return {"tokens": DummyCacheConfig()}

            @property
            def default_auth_cache(self) -> str:
                """Return default auth cache."""
                return "tokens"

        transport = HttpxSyncTransport.from_settings(_Settings())
        # No OAuth2 middleware — default_auth_cache silently unused.
        assert isinstance(transport._middlewares[0], BearerTokenAuthMiddleware)
        transport.close()

    async def test_async_no_cache_middleware_by_default(self) -> None:
        """Validate async no cache middleware by default."""
        transport = HttpxAsyncTransport.from_settings(HTTPSettings())
        types = [type(m) for m in transport._middlewares]
        assert AsyncCacheMiddleware not in types
        await transport.aclose()

    async def test_async_cache_backend_adds_async_cache_middleware(self) -> None:
        """Validate async cache backend adds async cache middleware."""
        s = self._settings_with_locmem_cache()
        transport = HttpxAsyncTransport.from_settings(s)
        assert isinstance(transport._middlewares[0], AsyncCacheMiddleware)
        await transport.aclose()

    async def test_async_auth_before_cache(self) -> None:
        """Validate async auth middleware is ordered before cache middleware."""
        s = self._settings_with_locmem_cache(
            auth_config=BearerAuthConfig(token=DUMMY_BEARER_TOKEN)
        )
        transport = HttpxAsyncTransport.from_settings(s)
        assert isinstance(transport._middlewares[0], AsyncBearerTokenAuthMiddleware)
        assert isinstance(transport._middlewares[1], AsyncCacheMiddleware)
        await transport.aclose()

    async def test_async_auth_cache_backend_sets_token_cache(self) -> None:
        """Validate async auth cache backend sets token cache."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def auth(self) -> OAuth2ClientCredentialsConfig:
                """Return auth."""
                return OAuth2ClientCredentialsConfig(
                    client_id=DUMMY_CLIENT_ID,
                    client_secret=DUMMY_CLIENT_SECRET,
                    token_url=DUMMY_TOKEN_URL,
                )

            @property
            def caches(self) -> dict[str, Any]:
                """Return caches."""
                return {"tokens": DummyCacheConfig()}

            @property
            def default_auth_cache(self) -> str:
                """Return default auth cache."""
                return "tokens"

        transport = HttpxAsyncTransport.from_settings(_Settings())
        mw = transport._middlewares[0]
        assert isinstance(mw, AsyncOAuth2ClientCredentialsMiddleware)
        assert isinstance(mw._cache, DummyCache)
        await transport.aclose()


class TestHttpxAsyncTransportOAuth2FromSettings:
    """Tests for async OAuth2 wiring in HttpxAsyncTransport.from_settings()."""

    async def test_oauth2_wired_async(self) -> None:
        """Validate oauth2 wired async."""
        transport = HttpxAsyncTransport.from_settings(_OAuth2Settings())
        assert isinstance(
            transport._middlewares[0], AsyncOAuth2ClientCredentialsMiddleware
        )
        await transport.aclose()

    async def test_oauth2_retry_still_last_async(self) -> None:
        """Validate oauth2 retry still last async."""
        transport = HttpxAsyncTransport.from_settings(_OAuth2Settings())
        assert isinstance(transport._middlewares[-1], AsyncRetryMiddleware)
        await transport.aclose()
