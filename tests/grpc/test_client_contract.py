"""Contract tests for the generic async gRPC client boundary."""

from __future__ import annotations

from typing import Any

import pytest

from plynth.grpc.client import AsyncGrpcClient, AsyncGrpcTransport
from plynth.grpc.settings import GrpcSettings


def _instantiate(cls: type[Any]) -> Any:
    """Instantiate a class using dynamic typing for abstract checks."""
    return cls()


class _RecordingTransport(AsyncGrpcTransport):
    """Minimal async transport that records unary call arguments."""

    def __init__(self) -> None:
        """Initialize recording transport state."""
        self.calls: list[dict[str, Any]] = []

    async def unary_unary(
        self,
        method: str,
        request: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Record call arguments and return a deterministic payload."""
        self.calls.append(
            {
                "method": method,
                "request": request,
                "metadata": metadata,
                "timeout": timeout,
            }
        )
        return {"ok": True}


class TestAsyncGrpcTransportContract:
    """Verify transport contract behavior for abstract and concrete classes."""

    def test_transport_is_abstract(self) -> None:
        """Validate abstract contract cannot be instantiated directly."""
        with pytest.raises(TypeError):
            _instantiate(AsyncGrpcTransport)


class TestAsyncGrpcClientContract:
    """Verify client-level call-shaping contracts."""

    async def test_unary_unary_normalizes_method_and_merges_metadata(self) -> None:
        """Validate method path normalization and metadata merge behavior."""
        transport = _RecordingTransport()
        client = AsyncGrpcClient(
            target="dns:///example.local:7443",
            transport=transport,
            metadata={"x-default": "a", "x-shared": "one"},
            timeout=12.0,
        )

        response = await client.unary_unary(
            "service.v1.Emitter/Subscribe",
            {"topic": "events"},
            metadata={"x-shared": "two", "x-call": "b"},
        )

        assert response == {"ok": True}
        assert transport.calls == [
            {
                "method": "/service.v1.Emitter/Subscribe",
                "request": {"topic": "events"},
                "metadata": {
                    "x-default": "a",
                    "x-shared": "two",
                    "x-call": "b",
                },
                "timeout": 12.0,
            }
        ]

    async def test_from_settings_uses_defaults_for_target_timeout_and_metadata(
        self,
    ) -> None:
        """Validate settings constructor wiring for runtime defaults."""
        settings = GrpcSettings(
            target="dns:///grpc.local:443",
            timeout=4.5,
            metadata={"authorization": "Bearer token"},
        )
        transport = _RecordingTransport()
        client = AsyncGrpcClient.from_settings(settings, transport=transport)

        await client.unary_unary("/svc.v1.Health/Check", {"ready": True})

        assert client.target == "dns:///grpc.local:443"
        assert transport.calls[0]["timeout"] == 4.5
        assert transport.calls[0]["metadata"] == {"authorization": "Bearer token"}

    async def test_rejects_empty_method_name(self) -> None:
        """Validate empty method names are rejected before transport call."""
        transport = _RecordingTransport()
        client = AsyncGrpcClient(target="dns:///x", transport=transport)

        with pytest.raises(ValueError, match="method must not be empty"):
            await client.unary_unary("   ", {})

        assert transport.calls == []
