"""Tests for ``plynth.adapters.django.drf.headers``."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from plynth.adapters.django.drf.headers import (
    build_async_request_header_middleware,
    build_request_header_middleware,
)
from plynth.base.request import Request
from plynth.base.response import Response


class TestBuildRequestHeaderMiddleware:
    """Verify request-header propagation behavior."""

    def test_propagates_default_correlation_headers(self) -> None:
        """Forward default request-id and trace headers when present."""
        incoming = SimpleNamespace(
            headers={
                "X-Request-Id": "req-123",
                "traceparent": "00-abc-xyz-01",
            }
        )
        middleware = build_request_header_middleware(incoming)

        outbound = Request(method="GET", url="https://api.example.test")

        def _next_handler(request: Request) -> Response:
            assert request.headers["X-Request-Id"] == "req-123"
            assert request.headers["traceparent"] == "00-abc-xyz-01"
            return Response(status_code=200, headers={}, content=b"")

        middleware.handle(outbound, _next_handler)

    def test_uses_custom_outbound_to_inbound_header_mapping(self) -> None:
        """Allow explicit outbound header names mapped from inbound headers."""
        incoming = SimpleNamespace(headers={"X-Tenant-Id": "tenant-a"})
        middleware = build_request_header_middleware(
            incoming,
            headers={"X-Upstream-Tenant": "X-Tenant-Id"},
        )

        outbound = Request(method="GET", url="https://api.example.test")

        def _next_handler(request: Request) -> Response:
            assert request.headers["X-Upstream-Tenant"] == "tenant-a"
            return Response(status_code=200, headers={}, content=b"")

        middleware.handle(outbound, _next_handler)

    def test_reads_lowercase_dict_headers_without_case_insensitive_mapping(
        self,
    ) -> None:
        """Read lowercase plain-dict headers through the fallback lookup path."""
        incoming = SimpleNamespace(headers={"x-request-id": "req-123"})
        middleware = build_request_header_middleware(incoming)

        outbound = Request(method="GET", url="https://api.example.test")

        def _next_handler(request: Request) -> Response:
            assert request.headers["X-Request-Id"] == "req-123"
            return Response(status_code=200, headers={}, content=b"")

        middleware.handle(outbound, _next_handler)

    def test_skips_headers_when_request_has_no_headers_mapping(self) -> None:
        """Return middleware with no injected headers for invalid request shape."""
        middleware = build_request_header_middleware(object())
        outbound = Request(method="GET", url="https://api.example.test")

        def _next_handler(request: Request) -> Response:
            assert request.headers == {}
            return Response(status_code=200, headers={}, content=b"")

        middleware.handle(outbound, _next_handler)

    def test_blocks_sensitive_headers_by_default(self) -> None:
        """Do not forward sensitive auth/session headers by default."""
        incoming = SimpleNamespace(
            headers={
                "Authorization": "Bearer secret",
                "X-Request-Id": "req-123",
            }
        )
        middleware = build_request_header_middleware(
            incoming,
            headers={
                "Authorization": "Authorization",
                "X-Request-Id": "X-Request-Id",
            },
        )

        outbound = Request(method="GET", url="https://api.example.test")

        def _next_handler(request: Request) -> Response:
            assert "Authorization" not in request.headers
            assert request.headers["X-Request-Id"] == "req-123"
            return Response(status_code=200, headers={}, content=b"")

        middleware.handle(outbound, _next_handler)

    def test_blocks_header_when_inbound_name_is_denied(self) -> None:
        """Do not forward headers when inbound name is in denylist."""
        incoming = SimpleNamespace(headers={"Authorization": "Bearer secret"})
        middleware = build_request_header_middleware(
            incoming,
            headers={"X-Upstream-Auth": "Authorization"},
        )

        outbound = Request(method="GET", url="https://api.example.test")

        def _next_handler(request: Request) -> Response:
            assert "X-Upstream-Auth" not in request.headers
            return Response(status_code=200, headers={}, content=b"")

        middleware.handle(outbound, _next_handler)

    def test_allows_sensitive_headers_when_denylist_is_empty(self) -> None:
        """Allow advanced opt-in by overriding denylist with an empty set."""
        incoming = SimpleNamespace(headers={"Authorization": "Bearer secret"})
        middleware = build_request_header_middleware(
            incoming,
            headers={"Authorization": "Authorization"},
            deny_headers=set(),
        )

        outbound = Request(method="GET", url="https://api.example.test")

        def _next_handler(request: Request) -> Response:
            assert request.headers["Authorization"] == "Bearer secret"
            return Response(status_code=200, headers={}, content=b"")

        middleware.handle(outbound, _next_handler)


class TestBuildAsyncRequestHeaderMiddleware:
    """Verify async request-header propagation behavior."""

    @pytest.mark.asyncio
    async def test_propagates_default_correlation_headers(self) -> None:
        """Forward default request-id and trace headers when present."""
        incoming = SimpleNamespace(
            headers={
                "X-Request-Id": "req-123",
                "traceparent": "00-abc-xyz-01",
            }
        )
        middleware = build_async_request_header_middleware(incoming)

        outbound = Request(method="GET", url="https://api.example.test")

        async def _next_handler(request: Request) -> Response:
            assert request.headers["X-Request-Id"] == "req-123"
            assert request.headers["traceparent"] == "00-abc-xyz-01"
            return Response(status_code=200, headers={}, content=b"")

        await middleware.handle(outbound, _next_handler)

    @pytest.mark.asyncio
    async def test_blocks_sensitive_headers_by_default(self) -> None:
        """Do not forward sensitive auth/session headers by default."""
        incoming = SimpleNamespace(
            headers={
                "Authorization": "Bearer secret",
                "X-Request-Id": "req-123",
            }
        )
        middleware = build_async_request_header_middleware(
            incoming,
            headers={
                "Authorization": "Authorization",
                "X-Request-Id": "X-Request-Id",
            },
        )

        outbound = Request(method="GET", url="https://api.example.test")

        async def _next_handler(request: Request) -> Response:
            assert "Authorization" not in request.headers
            assert request.headers["X-Request-Id"] == "req-123"
            return Response(status_code=200, headers={}, content=b"")

        await middleware.handle(outbound, _next_handler)

    @pytest.mark.asyncio
    async def test_uses_custom_outbound_to_inbound_header_mapping(self) -> None:
        """Allow explicit outbound header names mapped from inbound headers."""
        incoming = SimpleNamespace(headers={"X-Tenant-Id": "tenant-a"})
        middleware = build_async_request_header_middleware(
            incoming,
            headers={"X-Upstream-Tenant": "X-Tenant-Id"},
        )

        outbound = Request(method="GET", url="https://api.example.test")

        async def _next_handler(request: Request) -> Response:
            assert request.headers["X-Upstream-Tenant"] == "tenant-a"
            return Response(status_code=200, headers={}, content=b"")

        await middleware.handle(outbound, _next_handler)

    @pytest.mark.asyncio
    async def test_skips_headers_when_request_has_no_headers_mapping(self) -> None:
        """Return middleware with no injected headers for invalid request shape."""
        middleware = build_async_request_header_middleware(object())
        outbound = Request(method="GET", url="https://api.example.test")

        async def _next_handler(request: Request) -> Response:
            assert request.headers == {}
            return Response(status_code=200, headers={}, content=b"")

        await middleware.handle(outbound, _next_handler)

    @pytest.mark.asyncio
    async def test_allows_sensitive_headers_when_denylist_is_empty(self) -> None:
        """Allow advanced opt-in by overriding denylist with an empty set."""
        incoming = SimpleNamespace(headers={"Authorization": "Bearer secret"})
        middleware = build_async_request_header_middleware(
            incoming,
            headers={"Authorization": "Authorization"},
            deny_headers=set(),
        )

        outbound = Request(method="GET", url="https://api.example.test")

        async def _next_handler(request: Request) -> Response:
            assert request.headers["Authorization"] == "Bearer secret"
            return Response(status_code=200, headers={}, content=b"")

        await middleware.handle(outbound, _next_handler)
