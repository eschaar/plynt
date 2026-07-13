"""Tests for ``plynth.adapters.django.drf.headers``."""

from __future__ import annotations

from types import SimpleNamespace

from plynth.adapters.django.drf.headers import build_request_header_middleware
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

    def test_skips_headers_when_request_has_no_headers_mapping(self) -> None:
        """Return middleware with no injected headers for invalid request shape."""
        middleware = build_request_header_middleware(object())
        outbound = Request(method="GET", url="https://api.example.test")

        def _next_handler(request: Request) -> Response:
            assert request.headers == {}
            return Response(status_code=200, headers={}, content=b"")

        middleware.handle(outbound, _next_handler)
