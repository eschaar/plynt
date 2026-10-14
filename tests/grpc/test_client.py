"""Contract tests for the generic async gRPC client boundary."""

from __future__ import annotations

from typing import Any

import pytest

from plynt.grpc.client import AsyncGrpcClient, AsyncGrpcTransport
from plynt.grpc.handler import GrpcCall, NextGrpcHandler
from plynt.grpc.interceptor import AsyncGrpcInterceptor
from plynt.grpc.settings import GrpcSettings


def _instantiate(cls: type[Any]) -> Any:
    """Instantiate a class using dynamic typing for abstract checks."""
    return cls()


class _RecordingTransport(AsyncGrpcTransport):
    """Minimal async transport that records all call arguments."""

    def __init__(self) -> None:
        """Initialize recording transport state."""
        self.calls: list[dict[str, Any]] = []

    def _record(
        self,
        *,
        pattern: str,
        method: str,
        payload: Any,
        metadata: dict[str, str] | None,
        timeout: float | None,
    ) -> dict[str, Any]:
        """Record a transport call in a deterministic shape."""
        record = {
            "pattern": pattern,
            "method": method,
            "payload": payload,
            "metadata": metadata,
            "timeout": timeout,
        }
        self.calls.append(record)
        return record

    async def unary_unary(
        self,
        method: str,
        request: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Record call arguments and return a deterministic payload."""
        return self._record(
            pattern="unary_unary",
            method=method,
            payload=request,
            metadata=metadata,
            timeout=timeout,
        )

    async def unary_stream(
        self,
        method: str,
        request: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Record unary-stream call arguments and return a payload."""
        return self._record(
            pattern="unary_stream",
            method=method,
            payload=request,
            metadata=metadata,
            timeout=timeout,
        )

    async def stream_unary(
        self,
        method: str,
        requests: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Record stream-unary call arguments and return a payload."""
        return self._record(
            pattern="stream_unary",
            method=method,
            payload=requests,
            metadata=metadata,
            timeout=timeout,
        )

    async def stream_stream(
        self,
        method: str,
        requests: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Record stream-stream call arguments and return a payload."""
        return self._record(
            pattern="stream_stream",
            method=method,
            payload=requests,
            metadata=metadata,
            timeout=timeout,
        )


class _ClosableRecordingTransport(_RecordingTransport):
    """Recording transport that also supports async close semantics."""

    def __init__(self) -> None:
        """Initialize close tracking state."""
        super().__init__()
        self.closed = False

    async def close(self) -> None:
        """Record that close was called."""
        self.closed = True


class _SyncClosableRecordingTransport(_RecordingTransport):
    """Recording transport with a synchronous close method."""

    def __init__(self) -> None:
        """Initialize close tracking state."""
        super().__init__()
        self.closed = False

    def close(self) -> None:
        """Record that sync close was called."""
        self.closed = True


class _MetadataInterceptor(AsyncGrpcInterceptor):
    """Interceptor that enriches call metadata before forwarding."""

    def __init__(self, key: str, value: str) -> None:
        """Store metadata mutation values used during interception."""
        self._key = key
        self._value = value

    async def handle(self, call: GrpcCall, next_handler: NextGrpcHandler) -> Any:
        """Forward the call with one additional metadata entry."""
        call.metadata[self._key] = self._value
        return await next_handler(call)


class _OrderInterceptor(AsyncGrpcInterceptor):
    """Interceptor that records before/after ordering around the call."""

    def __init__(self, label: str, events: list[str]) -> None:
        """Persist mutable sink used for ordering assertions."""
        self._label = label
        self._events = events

    async def handle(self, call: GrpcCall, next_handler: NextGrpcHandler) -> Any:
        """Record around the downstream handler execution."""
        self._events.append(f"before:{self._label}")
        response = await next_handler(call)
        self._events.append(f"after:{self._label}")
        return response


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

        assert response == {
            "pattern": "unary_unary",
            "method": "/service.v1.Emitter/Subscribe",
            "payload": {"topic": "events"},
            "metadata": {
                "x-default": "a",
                "x-shared": "two",
                "x-call": "b",
            },
            "timeout": 12.0,
        }
        assert transport.calls == [
            {
                "pattern": "unary_unary",
                "method": "/service.v1.Emitter/Subscribe",
                "payload": {"topic": "events"},
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

    async def test_call_alias_delegates_to_unary_unary(self) -> None:
        """Validate semantic call alias routes to unary-unary transport."""
        transport = _RecordingTransport()
        client = AsyncGrpcClient(target="dns:///alias", transport=transport)

        response = await client.call("svc.v1.Health/Check", {"ready": True})

        assert response["pattern"] == "unary_unary"
        assert response["method"] == "/svc.v1.Health/Check"
        assert transport.calls[0]["pattern"] == "unary_unary"

    async def test_unary_stream_uses_shared_call_shaping(self) -> None:
        """Validate unary-stream call shaping parity with unary-unary."""
        transport = _RecordingTransport()
        client = AsyncGrpcClient(
            target="dns:///stream",
            transport=transport,
            metadata={"x-default": "a"},
            timeout=15.0,
        )

        response = await client.unary_stream(
            "svc.v1.Events/Subscribe",
            {"topic": "demo"},
            metadata={"x-call": "b"},
        )

        assert response == {
            "pattern": "unary_stream",
            "method": "/svc.v1.Events/Subscribe",
            "payload": {"topic": "demo"},
            "metadata": {"x-default": "a", "x-call": "b"},
            "timeout": 15.0,
        }

    async def test_stream_unary_uses_shared_call_shaping(self) -> None:
        """Validate stream-unary call shaping parity with unary-unary."""
        transport = _RecordingTransport()
        client = AsyncGrpcClient(
            target="dns:///stream",
            transport=transport,
            metadata={"x-default": "a"},
            timeout=8.0,
        )
        requests = [{"chunk": 1}, {"chunk": 2}]

        response = await client.stream_unary(
            "svc.v1.Upload/Commit",
            requests,
            metadata={"x-call": "b"},
            timeout=2.5,
        )

        assert response == {
            "pattern": "stream_unary",
            "method": "/svc.v1.Upload/Commit",
            "payload": requests,
            "metadata": {"x-default": "a", "x-call": "b"},
            "timeout": 2.5,
        }

    async def test_stream_stream_uses_shared_call_shaping(self) -> None:
        """Validate stream-stream call shaping parity with unary-unary."""
        transport = _RecordingTransport()
        client = AsyncGrpcClient(
            target="dns:///stream",
            transport=transport,
            metadata={"x-default": "a"},
            timeout=20.0,
        )
        requests = [{"seq": 1}, {"seq": 2}]

        response = await client.stream_stream(
            "svc.v1.Bidi/Exchange",
            requests,
            metadata={"x-call": "b"},
        )

        assert response == {
            "pattern": "stream_stream",
            "method": "/svc.v1.Bidi/Exchange",
            "payload": requests,
            "metadata": {"x-default": "a", "x-call": "b"},
            "timeout": 20.0,
        }

    async def test_rejects_empty_method_name(self) -> None:
        """Validate empty method names are rejected before transport call."""
        transport = _RecordingTransport()
        client = AsyncGrpcClient(target="dns:///x", transport=transport)

        with pytest.raises(ValueError, match="method must not be empty"):
            await client.unary_unary("   ", {})

        assert not transport.calls

    async def test_interceptors_mutate_metadata_before_transport_call(self) -> None:
        """Validate interceptor chain can enrich outbound metadata."""
        transport = _RecordingTransport()
        client = AsyncGrpcClient(
            target="dns:///grpc.local:443",
            transport=transport,
            metadata={"x-default": "base"},
            interceptors=(_MetadataInterceptor("x-interceptor", "yes"),),
        )

        await client.unary_unary("svc.v1.Health/Check", {"ready": True})

        assert transport.calls[0]["metadata"] == {
            "x-default": "base",
            "x-interceptor": "yes",
        }

    async def test_interceptors_wrap_in_declaration_order(self) -> None:
        """Validate declaration order controls wrapper execution order."""
        transport = _RecordingTransport()
        events: list[str] = []
        client = AsyncGrpcClient(
            target="dns:///grpc.local:443",
            transport=transport,
            interceptors=(
                _OrderInterceptor("first", events),
                _OrderInterceptor("second", events),
            ),
        )

        await client.unary_unary("svc.v1.Health/Check", {"ready": True})

        assert events == [
            "before:first",
            "before:second",
            "after:second",
            "after:first",
        ]

    async def test_close_calls_transport_close_when_available(self) -> None:
        """Validate lifecycle close delegates to the transport when supported."""
        transport = _ClosableRecordingTransport()
        client = AsyncGrpcClient(target="dns:///grpc.local:443", transport=transport)

        await client.close()

        assert transport.closed is True

    async def test_async_context_manager_closes_transport(self) -> None:
        """Validate context manager usage closes the underlying transport."""
        transport = _ClosableRecordingTransport()

        async with AsyncGrpcClient(
            target="dns:///grpc.local:443",
            transport=transport,
        ) as client:
            assert client.target == "dns:///grpc.local:443"

        assert transport.closed is True

    async def test_close_supports_synchronous_transport_close(self) -> None:
        """Validate close handles non-awaitable transport close methods."""
        transport = _SyncClosableRecordingTransport()
        client = AsyncGrpcClient(target="dns:///grpc.local:443", transport=transport)

        await client.close()

        assert transport.closed is True

    async def test_close_without_transport_cleanup_hook_preserves_usability(
        self,
    ) -> None:
        transport = _RecordingTransport()
        client = AsyncGrpcClient(target="dns:///grpc.local:443", transport=transport)

        await client.close()
        response = await client.unary_unary("/svc.v1.Health/Check", {"ready": True})

        assert response["payload"] == {"ready": True}
        assert len(transport.calls) == 1
