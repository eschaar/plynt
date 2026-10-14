"""Tests for BearerTokenAuthMiddleware and AsyncBearerTokenAuthMiddleware."""

from __future__ import annotations

from plynt.base.request import Request
from plynt.base.response import Response
from plynt.http.middleware.auth import (
    AsyncBearerTokenAuthMiddleware,
    BearerTokenAuthMiddleware,
)

# ---------------------------------------------------------------------------
# BearerTokenAuthMiddleware
# ---------------------------------------------------------------------------


class TestBearerTokenAuthMiddleware:
    """Test suite for BearerTokenAuthMiddleware."""

    def test_handle_sets_bearer_header(self) -> None:
        """Validate handle sets bearer header."""
        mw = BearerTokenAuthMiddleware("my-secret")
        req = Request(method="GET", url="https://example.com")
        mw.handle(req, lambda r: Response(status_code=200, content=b""))
        assert req.headers.get("Authorization") == "Bearer my-secret"

    def test_handle_calls_next_handler(self) -> None:
        """Validate handle calls next handler."""
        mw = BearerTokenAuthMiddleware("my-secret")
        req = Request(method="GET", url="https://example.com")
        called: list[Request] = []

        def _next(r: Request) -> Response:
            """Handle next."""
            called.append(r)
            return Response(status_code=200, content=b"")

        resp = mw.handle(req, _next)
        assert len(called) == 1
        assert resp.status_code == 200

    def test_different_tokens_produce_different_headers(self) -> None:
        """Validate different tokens produce different headers."""
        mw_a = BearerTokenAuthMiddleware("token-a")
        mw_b = BearerTokenAuthMiddleware("token-b")
        req_a = Request(method="GET", url="https://example.com")
        req_b = Request(method="GET", url="https://example.com")
        mw_a.handle(req_a, lambda r: Response(status_code=200, content=b""))
        mw_b.handle(req_b, lambda r: Response(status_code=200, content=b""))
        assert req_a.headers["Authorization"] != req_b.headers["Authorization"]


# ---------------------------------------------------------------------------
# AsyncBearerTokenAuthMiddleware
# ---------------------------------------------------------------------------


class TestAsyncBearerTokenAuthMiddleware:
    """Test suite for AsyncBearerTokenAuthMiddleware."""

    async def test_handle_sets_bearer_header(self) -> None:
        """Validate handle sets bearer header."""
        mw = AsyncBearerTokenAuthMiddleware("my-secret")
        req = Request(method="GET", url="https://example.com")

        async def _next(r: Request) -> Response:
            """Handle next."""
            return Response(status_code=200, content=b"")

        await mw.handle(req, _next)
        assert req.headers.get("Authorization") == "Bearer my-secret"

    async def test_handle_calls_next_handler(self) -> None:
        """Validate handle calls next handler."""
        mw = AsyncBearerTokenAuthMiddleware("tok")
        req = Request(method="GET", url="https://example.com")
        called: list[Request] = []

        async def _next(r: Request) -> Response:
            """Handle next."""
            called.append(r)
            return Response(status_code=200, content=b"")

        resp = await mw.handle(req, _next)
        assert len(called) == 1
        assert resp.status_code == 200
