"""Concrete async gRPC transport implementations for ``grpc.aio``.

This module provides the first production-oriented implementation of the
generic gRPC transport contract defined in :mod:`plynth.grpc.client`.

Design notes:

- The runtime dependency remains optional and is guarded lazily so importing
    :mod:`plynth.grpc` does not require ``grpcio`` unless a concrete channel is
    actually constructed.
- The transport stays protocol-level only. Salesforce-specific metadata,
    stubs, schema retrieval, and Avro decoding belong in the Salesforce CDC
    connector and are intentionally kept out of this module.
- A custom ``channel_factory`` can be injected for tests or alternative
    runtime wiring without changing the public transport contract.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from importlib import import_module
from importlib.util import find_spec
from inspect import isawaitable
from typing import Any

from plynth.grpc.client import AsyncGrpcTransport
from plynth.grpc.errors import GrpcStatusError, GrpcTransportError
from plynth.grpc.settings import GrpcSettings

__all__ = ["GrpcAioTransport", "ensure_grpc_runtime"]

try:  # pragma: no cover
    HAS_GRPC = find_spec("grpc") is not None
except ModuleNotFoundError:  # pragma: no cover
    HAS_GRPC = False

if not HAS_GRPC:  # pragma: no cover
    _GRPC_IMPORT_ERROR: Exception | None = ModuleNotFoundError("No module named 'grpc'")
else:  # pragma: no cover
    _GRPC_IMPORT_ERROR = None


def ensure_grpc_runtime() -> None:
    """Raise a clear runtime error when ``grpcio`` is unavailable.

    This keeps the optional-extra boundary explicit. Callers can import the
    generic gRPC package safely, and only transport construction fails when the
    runtime is missing.
    """
    if _GRPC_IMPORT_ERROR is not None:
        raise RuntimeError(
            "grpc runtime is not installed; install plynth[grpc] or add grpcio"
        ) from _GRPC_IMPORT_ERROR


def _load_grpc_runtime() -> Any:
    """Load and return the ``grpc`` runtime module on demand."""
    ensure_grpc_runtime()
    return import_module("grpc")


class GrpcAioTransport(AsyncGrpcTransport):
    """Execute generic async gRPC calls through ``grpc.aio`` channels.

    The class implements the four core RPC interaction patterns exposed by the
    generic :class:`~plynth.grpc.client.AsyncGrpcTransport` contract:

    - unary-unary
    - unary-stream
    - stream-unary
    - stream-stream

    The transport deliberately avoids generated stubs and protocol-specific
    request classes. Connector code supplies the method name, request objects,
    and metadata.
    """

    def __init__(
        self,
        *,
        target: str,
        secure: bool = True,
        channel_factory: Callable[..., Any] | None = None,
        credentials: Any | None = None,
        options: Sequence[tuple[str, str | int]] | None = None,
    ) -> None:
        """Initialize the transport and defer channel creation until first use.

        Args:
            target: gRPC endpoint such as ``dns:///host:7443``.
            secure: When ``True``, build a TLS channel.
            channel_factory: Optional injected channel constructor for tests or
                custom runtime integration.
            credentials: Optional prebuilt TLS credentials for secure channels.
            options: Optional low-level gRPC channel options.

        """
        self._target = target
        self._secure = secure
        self._channel_factory = channel_factory
        self._credentials = credentials
        self._options = tuple(options or ())
        self._channel: Any | None = None

    @classmethod
    def from_settings(
        cls,
        settings: GrpcSettings,
        *,
        channel_factory: Callable[..., Any] | None = None,
        credentials: Any | None = None,
        options: Sequence[tuple[str, str | int]] | None = None,
    ) -> GrpcAioTransport:
        """Build a concrete transport from ``GrpcSettings`` input."""
        return cls(
            target=settings.target,
            secure=settings.secure,
            channel_factory=channel_factory,
            credentials=credentials,
            options=options,
        )

    async def close(self) -> None:
        """Close the underlying channel when one was created.

        The transport keeps a single cached channel instance per transport
        object. Closing resets that cache so a later call can lazily rebuild a
        fresh channel if needed.
        """
        if self._channel is None:
            return

        maybe_result = self._channel.close()
        if isawaitable(maybe_result):
            await maybe_result
        self._channel = None

    async def unary_unary(
        self,
        method: str,
        request: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Execute a unary request and return a unary response.

        Any runtime failure is translated into the plynth gRPC error contract
        so callers do not depend on raw ``grpcio`` exceptions.
        """
        try:
            call = self._get_channel().unary_unary(method)
            return await call(
                request,
                metadata=self._build_metadata(metadata),
                timeout=timeout,
            )
        except Exception as exc:  # pragma: no cover - exercised in tests
            raise self._map_error(method, exc) from exc

    async def unary_stream(
        self,
        method: str,
        request: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Execute a unary request and return a response stream."""
        try:
            call = self._get_channel().unary_stream(method)
            return call(
                request,
                metadata=self._build_metadata(metadata),
                timeout=timeout,
            )
        except Exception as exc:  # pragma: no cover - exercised in tests
            raise self._map_error(method, exc) from exc

    async def stream_unary(
        self,
        method: str,
        requests: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Execute a request stream and return a unary response."""
        try:
            call = self._get_channel().stream_unary(method)
            return await call(
                requests,
                metadata=self._build_metadata(metadata),
                timeout=timeout,
            )
        except Exception as exc:  # pragma: no cover - exercised in tests
            raise self._map_error(method, exc) from exc

    async def stream_stream(
        self,
        method: str,
        requests: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Execute a bidirectional streaming call."""
        try:
            call = self._get_channel().stream_stream(method)
            return call(
                requests,
                metadata=self._build_metadata(metadata),
                timeout=timeout,
            )
        except Exception as exc:  # pragma: no cover - exercised in tests
            raise self._map_error(method, exc) from exc

    def _get_channel(self) -> Any:
        """Return a cached ``grpc.aio`` channel instance.

        The first transport call constructs the channel; all later calls reuse
        it until :meth:`close` is invoked.
        """
        if self._channel is None:
            self._channel = self._build_channel()
        return self._channel

    def _build_channel(self) -> Any:
        """Create a configured gRPC channel instance.

        Secure channels are the default because Salesforce Pub/Sub requires a
        secure channel over SSL/TLS.
        """
        factory = self._channel_factory
        if factory is None:
            grpc = _load_grpc_runtime()
            if self._secure:
                credentials = self._credentials or grpc.ssl_channel_credentials()
                factory = grpc.aio.secure_channel
                return factory(self._target, credentials, options=self._options)
            factory = grpc.aio.insecure_channel
        return factory(self._target, options=self._options)

    @staticmethod
    def _build_metadata(
        metadata: dict[str, str] | None,
    ) -> tuple[tuple[str, str], ...] | None:
        """Convert metadata mapping into the ``grpc.aio`` metadata shape."""
        if not metadata:
            return None
        return tuple(metadata.items())

    @staticmethod
    def _map_error(method: str, exc: Exception) -> Exception:
        """Translate ``grpcio`` runtime errors into plynth error contracts.

        ``grpcio`` status objects vary slightly by runtime shape. Some expose
        an enum-like ``value`` tuple, others behave more like direct integer
        status codes. This mapper normalizes both into the stable plynth error
        contract.
        """
        code_attr = getattr(exc, "code", None)
        details_attr = getattr(exc, "details", None)

        status_code = None
        code_name = None
        if callable(code_attr):
            code_value = code_attr()
            raw_code_name = getattr(code_value, "name", None)
            if isinstance(raw_code_name, str):
                code_name = raw_code_name

            # Enum-like status codes expose an internal tuple whose first item
            # is the numeric gRPC status code.
            enum_value = getattr(code_value, "value", None)
            if isinstance(enum_value, tuple):
                if enum_value and isinstance(enum_value[0], int):
                    status_code = enum_value[0]
            elif isinstance(code_value, int):
                status_code = code_value

        details = details_attr() if callable(details_attr) else None
        message = details if isinstance(details, str) and details else str(exc) or None
        if status_code is not None:
            return GrpcStatusError(
                message,
                status_code=status_code,
                method=method,
                grpc_status_name=code_name,
            )

        return GrpcTransportError(
            message,
            method=method,
            underlying_error=str(exc),
        )
