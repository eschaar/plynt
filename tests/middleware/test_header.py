"""Tests for plynt.middleware.header (HeaderMiddleware, AsyncHeaderMiddleware)."""

from __future__ import annotations

import pytest

from plynt.base.middleware import AsyncMiddleware, SyncMiddleware
from plynt.base.request import Request
from plynt.base.response import Response
from plynt.middleware.header import AsyncHeaderMiddleware, HeaderMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RESPONSE = Response(status_code=200, content=b"ok")


def _noop(request: Request) -> Response:
    """Handle noop."""
    return _RESPONSE


async def _async_noop(request: Request) -> Response:
    """Handle async noop."""
    return _RESPONSE


def _make_request(**kwargs: object) -> Request:
    """Handle make request."""
    return Request(method="GET", url="https://example.com/api", **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestHeaderMiddleware
# ---------------------------------------------------------------------------


class TestHeaderMiddleware:
    """Tests for the synchronous HeaderMiddleware (ADR-0015)."""

    def test_satisfies_sync_middleware_protocol(self) -> None:
        """Validate satisfies sync middleware protocol."""
        assert isinstance(HeaderMiddleware({}), SyncMiddleware)

    def test_injects_static_header(self) -> None:
        """Validate injects static header."""
        mw = HeaderMiddleware({"User-Agent": "test/1.0"})
        captured: list[Request] = []

        def handler(req: Request) -> Response:
            """Return handler."""
            captured.append(req)
            return _RESPONSE

        mw.handle(_make_request(), handler)
        assert captured[0].headers["User-Agent"] == "test/1.0"

    def test_callable_value_evaluated_per_request(self) -> None:
        """Validate callable value evaluated per request."""
        counter = {"n": 0}

        def make_id() -> str:
            """Return make id."""
            counter["n"] += 1
            return f"id-{counter['n']}"

        mw = HeaderMiddleware({"X-Request-ID": make_id})
        captured: list[Request] = []

        def handler(req: Request) -> Response:
            """Return handler."""
            captured.append(
                Request(method=req.method, url=req.url, headers=dict(req.headers))
            )
            return _RESPONSE

        mw.handle(_make_request(), handler)
        mw.handle(_make_request(), handler)

        assert captured[0].headers["X-Request-ID"] == "id-1"
        assert captured[1].headers["X-Request-ID"] == "id-2"

    def test_does_not_overwrite_existing_header(self) -> None:
        """Validate does not overwrite existing header."""
        mw = HeaderMiddleware({"X-Correlation-ID": "mw-value"})
        req = _make_request(headers={"X-Correlation-ID": "caller-value"})
        captured: list[Request] = []

        def handler(r: Request) -> Response:
            """Return handler."""
            captured.append(r)
            return _RESPONSE

        mw.handle(req, handler)
        assert captured[0].headers["X-Correlation-ID"] == "caller-value"

    def test_injects_multiple_headers(self) -> None:
        """Validate injects multiple headers."""
        mw = HeaderMiddleware(
            {
                "User-Agent": "svc/1.0",
                "Accept-Language": "en",
                "X-Tenant-ID": "acme",
            }
        )
        captured: list[Request] = []

        def handler(req: Request) -> Response:
            """Return handler."""
            captured.append(req)
            return _RESPONSE

        mw.handle(_make_request(), handler)
        assert captured[0].headers["User-Agent"] == "svc/1.0"
        assert captured[0].headers["Accept-Language"] == "en"
        assert captured[0].headers["X-Tenant-ID"] == "acme"

    def test_returns_response_from_next_handler(self) -> None:
        """Validate returns response from next handler."""
        expected = Response(status_code=201, content=b"created")
        mw = HeaderMiddleware({"User-Agent": "svc/1.0"})
        result = mw.handle(_make_request(), lambda r: expected)
        assert result is expected

    def test_empty_headers_dict_is_a_passthrough(self) -> None:
        """Validate empty headers dict is a passthrough."""
        mw = HeaderMiddleware({})
        req = _make_request(headers={"Authorization": "Bearer tok"})
        captured: list[Request] = []

        def handler(r: Request) -> Response:
            """Return handler."""
            captured.append(r)
            return _RESPONSE

        mw.handle(req, handler)
        assert captured[0].headers == {"Authorization": "Bearer tok"}

    def test_partial_overwrite_protection(self) -> None:
        """Pre-set header is kept; absent header is injected."""
        mw = HeaderMiddleware(
            {
                "X-Correlation-ID": "mw-id",
                "User-Agent": "svc/1.0",
            }
        )
        req = _make_request(headers={"X-Correlation-ID": "caller-id"})
        captured: list[Request] = []

        def handler(r: Request) -> Response:
            """Return handler."""
            captured.append(r)
            return _RESPONSE

        mw.handle(req, handler)
        assert captured[0].headers["X-Correlation-ID"] == "caller-id"
        assert captured[0].headers["User-Agent"] == "svc/1.0"

    def test_api_key_auth_via_header_middleware(self) -> None:
        """HeaderMiddleware can serve as lightweight API key auth (ADR-0015)."""
        mw = HeaderMiddleware({"X-Api-Key": "secret-key"})
        captured: list[Request] = []

        def handler(req: Request) -> Response:
            """Return handler."""
            captured.append(req)
            return _RESPONSE

        mw.handle(_make_request(), handler)
        assert captured[0].headers["X-Api-Key"] == "secret-key"


# ---------------------------------------------------------------------------
# TestAsyncHeaderMiddleware
# ---------------------------------------------------------------------------


class TestAsyncHeaderMiddleware:
    """Tests for the asynchronous AsyncHeaderMiddleware (ADR-0015)."""

    def test_satisfies_async_middleware_protocol(self) -> None:
        """Validate satisfies async middleware protocol."""
        assert isinstance(AsyncHeaderMiddleware({}), AsyncMiddleware)

    @pytest.mark.asyncio
    async def test_injects_static_header(self) -> None:
        """Validate injects static header."""
        mw = AsyncHeaderMiddleware({"User-Agent": "test/1.0"})
        captured: list[Request] = []

        async def handler(req: Request) -> Response:
            """Return handler."""
            captured.append(req)
            return _RESPONSE

        await mw.handle(_make_request(), handler)
        assert captured[0].headers["User-Agent"] == "test/1.0"

    @pytest.mark.asyncio
    async def test_callable_value_evaluated_per_request(self) -> None:
        """Validate callable value evaluated per request."""
        counter = {"n": 0}

        def make_id() -> str:
            """Return make id."""
            counter["n"] += 1
            return f"id-{counter['n']}"

        mw = AsyncHeaderMiddleware({"X-Request-ID": make_id})
        captured: list[Request] = []

        async def handler(req: Request) -> Response:
            """Return handler."""
            captured.append(
                Request(method=req.method, url=req.url, headers=dict(req.headers))
            )
            return _RESPONSE

        await mw.handle(_make_request(), handler)
        await mw.handle(_make_request(), handler)

        assert captured[0].headers["X-Request-ID"] == "id-1"
        assert captured[1].headers["X-Request-ID"] == "id-2"

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing_header(self) -> None:
        """Validate does not overwrite existing header."""
        mw = AsyncHeaderMiddleware({"X-Correlation-ID": "mw-value"})
        req = _make_request(headers={"X-Correlation-ID": "caller-value"})
        captured: list[Request] = []

        async def handler(r: Request) -> Response:
            """Return handler."""
            captured.append(r)
            return _RESPONSE

        await mw.handle(req, handler)
        assert captured[0].headers["X-Correlation-ID"] == "caller-value"

    @pytest.mark.asyncio
    async def test_returns_response_from_next_handler(self) -> None:
        """Validate returns response from next handler."""
        expected = Response(status_code=202, content=b"accepted")
        mw = AsyncHeaderMiddleware({"User-Agent": "svc/1.0"})

        async def handler(r: Request) -> Response:
            """Return handler."""
            return expected

        result = await mw.handle(_make_request(), handler)
        assert result is expected

    @pytest.mark.asyncio
    async def test_empty_headers_dict_is_a_passthrough(self) -> None:
        """Validate empty headers dict is a passthrough."""
        mw = AsyncHeaderMiddleware({})
        req = _make_request(headers={"Authorization": "Bearer tok"})
        captured: list[Request] = []

        async def handler(r: Request) -> Response:
            """Return handler."""
            captured.append(r)
            return _RESPONSE

        await mw.handle(req, handler)
        assert captured[0].headers == {"Authorization": "Bearer tok"}
