"""Focused contract tests for the concrete async gRPC transport.

The real transport depends on ``grpcio`` and runtime channel objects. These
tests keep that dependency boundary explicit by using small fake channels and
runtime shims that exercise the plynth contract without opening network
connections.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from plynth.grpc import transport as grpc_transport
from plynth.grpc.errors import GrpcStatusError, GrpcTransportError
from plynth.grpc.settings import GrpcSettings
from plynth.grpc.transport import GrpcAioTransport


@dataclass
class _FakeStatusCode:
    """Small enum-like stand-in for grpc status code objects."""

    name: str
    value: tuple[int, str]


class _FakeRpcError(Exception):
    """Test double that mimics the grpc error interface we consume."""

    def __init__(self, status_code: _FakeStatusCode | None, details: str) -> None:
        """Store fake status and detail values for mapping tests."""
        super().__init__(details)
        self._status_code = status_code
        self._details = details

    def code(self) -> Any:
        """Return the fake grpc status value."""
        return self._status_code

    def details(self) -> str:
        """Return the fake grpc detail string."""
        return self._details


class _UnaryUnaryCall:
    """Unary-unary fake call object for the channel double."""

    def __init__(self, channel: _FakeChannel) -> None:
        """Bind the fake call object to its channel recorder."""
        self._channel = channel

    async def __call__(
        self,
        request: Any,
        *,
        metadata: tuple[tuple[str, str], ...] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Record the call or raise a configured fake runtime error."""
        if self._channel.error is not None:
            raise self._channel.error
        record = {
            "pattern": "unary_unary",
            "request": request,
            "metadata": metadata,
            "timeout": timeout,
        }
        self._channel.records.append(record)
        return record


class _UnaryStreamCall:
    """Unary-stream fake call object for the channel double."""

    def __init__(self, channel: _FakeChannel) -> None:
        """Bind the fake call object to its channel recorder."""
        self._channel = channel

    def __call__(
        self,
        request: Any,
        *,
        metadata: tuple[tuple[str, str], ...] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Record the streaming call metadata and request payload."""
        record = {
            "pattern": "unary_stream",
            "request": request,
            "metadata": metadata,
            "timeout": timeout,
        }
        self._channel.records.append(record)
        return record


class _StreamUnaryCall:
    """Stream-unary fake call object for the channel double."""

    def __init__(self, channel: _FakeChannel) -> None:
        """Bind the fake call object to its channel recorder."""
        self._channel = channel

    async def __call__(
        self,
        requests: Any,
        *,
        metadata: tuple[tuple[str, str], ...] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Record the request stream and return a deterministic payload."""
        record = {
            "pattern": "stream_unary",
            "request": requests,
            "metadata": metadata,
            "timeout": timeout,
        }
        self._channel.records.append(record)
        return record


class _StreamStreamCall:
    """Bidirectional fake call object for the channel double."""

    def __init__(self, channel: _FakeChannel) -> None:
        """Bind the fake call object to its channel recorder."""
        self._channel = channel

    def __call__(
        self,
        requests: Any,
        *,
        metadata: tuple[tuple[str, str], ...] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Record the bidi stream request shape and metadata."""
        record = {
            "pattern": "stream_stream",
            "request": requests,
            "metadata": metadata,
            "timeout": timeout,
        }
        self._channel.records.append(record)
        return record


class _FakeChannel:
    """Record method selection and emulate a ``grpc.aio`` channel."""

    def __init__(self) -> None:
        """Initialize empty call records and optional error injection."""
        self.records: list[dict[str, Any]] = []
        self.methods: list[tuple[str, str]] = []
        self.closed = False
        self.error: Exception | None = None

    def unary_unary(self, method: str) -> _UnaryUnaryCall:
        """Return the fake unary-unary call object for ``method``."""
        self.methods.append(("unary_unary", method))
        return _UnaryUnaryCall(self)

    def unary_stream(self, method: str) -> _UnaryStreamCall:
        """Return the fake unary-stream call object for ``method``."""
        self.methods.append(("unary_stream", method))
        return _UnaryStreamCall(self)

    def stream_unary(self, method: str) -> _StreamUnaryCall:
        """Return the fake stream-unary call object for ``method``."""
        self.methods.append(("stream_unary", method))
        return _StreamUnaryCall(self)

    def stream_stream(self, method: str) -> _StreamStreamCall:
        """Return the fake stream-stream call object for ``method``."""
        self.methods.append(("stream_stream", method))
        return _StreamStreamCall(self)

    async def close(self) -> None:
        """Mark the fake channel as closed."""
        self.closed = True


class _FakeAioRuntime:
    """Stand-in for the ``grpc.aio`` namespace used by the transport."""

    def __init__(self, channel: _FakeChannel) -> None:
        """Store the channel returned by fake channel factories."""
        self.channel = channel
        self.calls: list[tuple[str, str, Any, tuple[tuple[str, str | int], ...]]] = []

    def secure_channel(
        self,
        target: str,
        credentials: Any,
        *,
        options: tuple[tuple[str, str | int], ...],
    ) -> _FakeChannel:
        """Record secure-channel construction and return the fake channel."""
        self.calls.append(("secure", target, credentials, options))
        return self.channel

    def insecure_channel(
        self,
        target: str,
        *,
        options: tuple[tuple[str, str | int], ...],
    ) -> _FakeChannel:
        """Record insecure-channel construction and return the fake channel."""
        self.calls.append(("insecure", target, None, options))
        return self.channel


class _FakeGrpcRuntime:
    """Runtime shim exposing the pieces of ``grpc`` the transport needs."""

    def __init__(self, channel: _FakeChannel) -> None:
        """Expose a fake ``aio`` namespace backed by one fake channel."""
        self.aio = _FakeAioRuntime(channel)

    @staticmethod
    def ssl_channel_credentials() -> str:
        """Return a deterministic fake credential marker."""
        return "ssl-creds"


class TestGrpcAioTransport:
    """Verify concrete grpc.aio transport behavior."""

    @pytest.mark.asyncio
    async def test_close_without_channel_is_a_noop(self) -> None:
        """Allow close calls before any channel is created."""
        transport = GrpcAioTransport(target="dns:///pubsub.salesforce.com:7443")

        await transport.close()

    @pytest.mark.asyncio
    async def test_from_settings_uses_secure_channel_and_metadata_shape(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Build secure channels from settings and pass metadata tuples."""
        channel = _FakeChannel()
        runtime = _FakeGrpcRuntime(channel)
        monkeypatch.setattr(grpc_transport, "_GRPC_IMPORT_ERROR", None)
        monkeypatch.setattr(grpc_transport, "_load_grpc_runtime", lambda: runtime)

        transport = GrpcAioTransport.from_settings(
            GrpcSettings(target="dns:///pubsub.salesforce.com:7443", secure=True),
            options=(("grpc.keepalive_time_ms", 30000),),
        )

        response = await transport.unary_unary(
            "/eventbus.v1.PubSub/Subscribe",
            {"topic": "/data/AccountChangeEvent"},
            metadata={"accesstoken": "token", "tenantid": "00Dxx"},
            timeout=5.0,
        )

        assert runtime.aio.calls == [
            (
                "secure",
                "dns:///pubsub.salesforce.com:7443",
                "ssl-creds",
                (("grpc.keepalive_time_ms", 30000),),
            )
        ]
        assert channel.methods == [("unary_unary", "/eventbus.v1.PubSub/Subscribe")]
        assert response["metadata"] == (
            ("accesstoken", "token"),
            ("tenantid", "00Dxx"),
        )
        await transport.close()
        assert channel.closed is True

    @pytest.mark.asyncio
    async def test_uses_insecure_channel_when_requested(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Build insecure channels when settings disable TLS."""
        channel = _FakeChannel()
        runtime = _FakeGrpcRuntime(channel)
        monkeypatch.setattr(grpc_transport, "_GRPC_IMPORT_ERROR", None)
        monkeypatch.setattr(grpc_transport, "_load_grpc_runtime", lambda: runtime)

        transport = GrpcAioTransport(
            target="dns:///localhost:7443",
            secure=False,
        )

        await transport.unary_stream(
            "/eventbus.v1.PubSub/Subscribe",
            {"topic": "/data/ChangeEvents"},
        )

        assert runtime.aio.calls == [("insecure", "dns:///localhost:7443", None, ())]

    @pytest.mark.asyncio
    async def test_stream_unary_and_stream_stream_forward_requests(self) -> None:
        """Forward stream call shapes through the concrete channel methods."""
        channel = _FakeChannel()
        transport = GrpcAioTransport(
            target="dns:///pubsub.salesforce.com:7443",
            channel_factory=lambda target, options=(): channel,
        )

        response = await transport.stream_unary(
            "/eventbus.v1.PubSub/Publish",
            [{"payload": b"1"}, {"payload": b"2"}],
            metadata={"accesstoken": "token"},
            timeout=3.0,
        )
        stream = await transport.stream_stream(
            "/eventbus.v1.PubSub/Subscribe",
            [{"num_requested": 10}],
            metadata={"tenantid": "00Dxx"},
            timeout=7.0,
        )

        assert response["pattern"] == "stream_unary"
        assert stream["pattern"] == "stream_stream"
        assert channel.methods == [
            ("stream_unary", "/eventbus.v1.PubSub/Publish"),
            ("stream_stream", "/eventbus.v1.PubSub/Subscribe"),
        ]

    @pytest.mark.asyncio
    async def test_maps_grpc_status_errors(self) -> None:
        """Map grpc status failures into the plynth status error contract."""
        channel = _FakeChannel()
        channel.error = _FakeRpcError(
            _FakeStatusCode("UNAVAILABLE", (14, "unavailable")),
            "upstream unavailable",
        )
        transport = GrpcAioTransport(
            target="dns:///pubsub.salesforce.com:7443",
            channel_factory=lambda target, options=(): channel,
        )

        with pytest.raises(GrpcStatusError) as exc_info:
            await transport.unary_unary(
                "/eventbus.v1.PubSub/GetSchema",
                {"schema_id": "abc"},
            )

        assert exc_info.value.status_code == 14
        assert exc_info.value.method == "/eventbus.v1.PubSub/GetSchema"
        assert exc_info.value.details is not None
        assert exc_info.value.details["grpc_status_name"] == "UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_maps_integer_status_codes(self) -> None:
        """Map direct integer status codes into the status error contract."""
        channel = _FakeChannel()
        channel.error = _FakeRpcError(None, "deadline exceeded")
        channel.error.code = lambda: 4  # type: ignore[method-assign]
        transport = GrpcAioTransport(
            target="dns:///pubsub.salesforce.com:7443",
            channel_factory=lambda target, options=(): channel,
        )

        with pytest.raises(GrpcStatusError) as exc_info:
            await transport.unary_unary(
                "/eventbus.v1.PubSub/GetSchema",
                {"schema_id": "abc"},
            )

        assert exc_info.value.status_code == 4

    @pytest.mark.asyncio
    async def test_maps_non_status_failures_to_transport_error(self) -> None:
        """Map generic runtime errors to the transport error contract."""
        channel = _FakeChannel()
        channel.error = RuntimeError("socket closed")
        transport = GrpcAioTransport(
            target="dns:///pubsub.salesforce.com:7443",
            channel_factory=lambda target, options=(): channel,
        )

        with pytest.raises(GrpcTransportError) as exc_info:
            await transport.unary_unary(
                "/eventbus.v1.PubSub/GetSchema",
                {"schema_id": "abc"},
            )

        assert exc_info.value.details is not None
        assert exc_info.value.details["method"] == "/eventbus.v1.PubSub/GetSchema"


class TestGrpcRuntimeGuard:
    """Verify runtime guard behavior for the grpc extra."""

    def test_load_grpc_runtime_imports_module(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Load the grpc module through the lazy runtime helper."""
        sentinel = object()
        monkeypatch.setattr(grpc_transport, "_GRPC_IMPORT_ERROR", None)
        monkeypatch.setattr(grpc_transport, "import_module", lambda name: sentinel)

        loaded = grpc_transport._load_grpc_runtime()  # pyright: ignore[reportPrivateUsage]  # pylint: disable=protected-access

        assert loaded is sentinel

    def test_raises_clear_error_when_grpc_runtime_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Return a clear error message when grpcio is unavailable."""
        monkeypatch.setattr(
            grpc_transport,
            "_GRPC_IMPORT_ERROR",
            ModuleNotFoundError("No module named 'grpc'"),
        )

        with pytest.raises(RuntimeError, match="grpc runtime is not installed"):
            grpc_transport.ensure_grpc_runtime()
