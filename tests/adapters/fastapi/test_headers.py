"""Tests for FastAPI header propagation helpers."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

pytest.importorskip("fastapi")

from plynt.adapters.fastapi.headers import (
    build_async_request_header_middleware,
    build_request_header_middleware,
)


@dataclass
class _RequestStub:
    """Minimal request-like object with a headers mapping."""

    headers: dict[str, str]


class TestFastAPIHeaderHelpers:
    """Validate request-header middleware builders for FastAPI adapter."""

    def test_build_request_header_middleware_resolves_default_headers(self) -> None:
        """Forward default correlation and tracing headers."""
        request = _RequestStub(
            headers={
                "X-Request-Id": "req-1",
                "traceparent": "00-abc",
            }
        )

        middleware = build_request_header_middleware(request)
        assert middleware._headers == {  # pylint: disable=protected-access
            "X-Request-Id": "req-1",
            "traceparent": "00-abc",
        }

    def test_denylist_blocks_sensitive_header_forwarding(self) -> None:
        """Do not propagate denied or sensitive headers by default."""
        request = _RequestStub(headers={"authorization": "Bearer secret"})

        middleware = build_request_header_middleware(
            request,
            headers={"Authorization": "authorization"},
        )
        assert middleware._headers == {}  # pylint: disable=protected-access

    def test_async_builder_uses_same_header_resolution(self) -> None:
        """Build async middleware with the same resolved header map."""
        request = _RequestStub(headers={"X-Correlation-Id": "corr-1"})

        middleware = build_async_request_header_middleware(request)
        assert middleware._headers == {  # pylint: disable=protected-access
            "X-Correlation-Id": "corr-1",
        }

    def test_builder_handles_request_without_headers_mapping(self) -> None:
        """Return empty resolved header set for non-mapping request headers."""
        middleware = build_request_header_middleware(object())
        assert middleware._headers == {}  # pylint: disable=protected-access

    def test_denylist_blocks_when_inbound_header_name_is_sensitive(self) -> None:
        """Drop mapping when inbound header name is denylisted."""
        request = _RequestStub(headers={"authorization": "Bearer secret"})

        middleware = build_request_header_middleware(
            request,
            headers={"X-Upstream-Auth": "authorization"},
        )

        assert middleware._headers == {}  # pylint: disable=protected-access
