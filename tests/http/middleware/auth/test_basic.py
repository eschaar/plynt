"""Tests for BasicAuthMiddleware and AsyncBasicAuthMiddleware."""

from __future__ import annotations

import base64

from plynth.base.request import Request
from plynth.base.response import Response
from plynth.http.middleware.auth import (
    AsyncBasicAuthMiddleware,
    BasicAuthMiddleware,
)

# ---------------------------------------------------------------------------
# BasicAuthMiddleware
# ---------------------------------------------------------------------------


class TestBasicAuthMiddleware:
    """Test suite for BasicAuthMiddleware."""

    def test_handle_sets_basic_header(self) -> None:
        """Validate handle sets basic header."""
        mw = BasicAuthMiddleware("user", "pass")
        expected = base64.b64encode(b"user:pass").decode()
        req = Request(method="GET", url="https://example.com")
        mw.handle(req, lambda r: Response(status_code=200, content=b""))
        assert req.headers.get("Authorization") == f"Basic {expected}"

    def test_handle_calls_next_handler(self) -> None:
        """Validate handle calls next handler."""
        mw = BasicAuthMiddleware("user", "pass")
        req = Request(method="GET", url="https://example.com")
        called: list[Request] = []

        def _next(r: Request) -> Response:
            """Handle next."""
            called.append(r)
            return Response(status_code=200, content=b"")

        resp = mw.handle(req, _next)
        assert len(called) == 1
        assert resp.status_code == 200

    def test_different_credentials_produce_different_headers(self) -> None:
        """Validate different credentials produce different headers."""
        mw_a = BasicAuthMiddleware("alice", "secret1")
        mw_b = BasicAuthMiddleware("bob", "secret2")
        req_a = Request(method="GET", url="https://example.com")
        req_b = Request(method="GET", url="https://example.com")
        mw_a.handle(req_a, lambda r: Response(status_code=200, content=b""))
        mw_b.handle(req_b, lambda r: Response(status_code=200, content=b""))
        assert req_a.headers["Authorization"] != req_b.headers["Authorization"]


# ---------------------------------------------------------------------------
# AsyncBasicAuthMiddleware
# ---------------------------------------------------------------------------


class TestAsyncBasicAuthMiddleware:
    """Test suite for AsyncBasicAuthMiddleware."""

    async def test_handle_sets_basic_header(self) -> None:
        """Validate handle sets basic header."""
        mw = AsyncBasicAuthMiddleware("user", "pass")
        expected = base64.b64encode(b"user:pass").decode()
        req = Request(method="GET", url="https://example.com")

        async def _next(r: Request) -> Response:
            """Handle next."""
            return Response(status_code=200, content=b"")

        await mw.handle(req, _next)
        assert req.headers.get("Authorization") == f"Basic {expected}"

    async def test_handle_calls_next_handler(self) -> None:
        """Validate handle calls next handler."""
        mw = AsyncBasicAuthMiddleware("user", "pass")
        req = Request(method="GET", url="https://example.com")
        called: list[Request] = []

        async def _next(r: Request) -> Response:
            """Handle next."""
            called.append(r)
            return Response(status_code=200, content=b"")

        resp = await mw.handle(req, _next)
        assert len(called) == 1
        assert resp.status_code == 200
