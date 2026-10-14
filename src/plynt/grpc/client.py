"""Generic async-first gRPC client abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from inspect import isawaitable
from typing import Any

from plynt.grpc.handler import GrpcCall, NextGrpcHandler
from plynt.grpc.interceptor import AsyncGrpcInterceptor
from plynt.grpc.settings import GrpcSettings

__all__ = ["AsyncGrpcClient", "AsyncGrpcTransport"]


class AsyncGrpcTransport(ABC):
    """Contract for async gRPC transport implementations."""

    @abstractmethod
    async def unary_unary(
        self,
        method: str,
        request: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:  # pragma: no cover
        """Execute a unary request and return the raw response."""

    @abstractmethod
    async def unary_stream(
        self,
        method: str,
        request: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:  # pragma: no cover
        """Execute a unary request and return a response stream."""

    @abstractmethod
    async def stream_unary(
        self,
        method: str,
        requests: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:  # pragma: no cover
        """Execute a request stream and return a unary response."""

    @abstractmethod
    async def stream_stream(
        self,
        method: str,
        requests: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:  # pragma: no cover
        """Execute a bidirectional streaming call."""


class AsyncGrpcClient:
    """Async client wrapper around an ``AsyncGrpcTransport`` implementation."""

    def __init__(
        self,
        *,
        target: str,
        transport: AsyncGrpcTransport,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
        interceptors: tuple[AsyncGrpcInterceptor, ...] = (),
    ) -> None:
        """Initialize AsyncGrpcClient."""
        self._target = target
        self._transport = transport
        self._metadata = metadata or {}
        self._timeout = timeout
        self._interceptors = interceptors

    @classmethod
    def from_settings(
        cls,
        settings: GrpcSettings,
        *,
        transport: AsyncGrpcTransport,
        interceptors: tuple[AsyncGrpcInterceptor, ...] = (),
    ) -> AsyncGrpcClient:
        """Build a client from a ``GrpcSettings`` instance."""
        return cls(
            target=settings.target,
            transport=transport,
            metadata=settings.metadata,
            timeout=settings.timeout,
            interceptors=interceptors,
        )

    async def __aenter__(self) -> AsyncGrpcClient:
        """Return this client as an async context manager."""
        return self

    async def __aexit__(self, *_: object) -> None:
        """Close the underlying transport on context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the transport when it exposes a ``close`` method."""
        close_method = getattr(self._transport, "close", None)
        if not callable(close_method):
            return

        maybe_result = close_method()
        if isawaitable(maybe_result):
            await maybe_result

    @property
    def target(self) -> str:
        """Return the configured target endpoint."""
        return self._target

    async def unary_unary(
        self,
        method: str,
        request: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Execute a unary call through the underlying transport."""
        normalized_method, merged_metadata, resolved_timeout = self._prepare_call(
            method=method,
            metadata=metadata,
            timeout=timeout,
        )
        call = GrpcCall(
            method=normalized_method,
            request=request,
            metadata=merged_metadata,
            timeout=resolved_timeout,
        )
        return await self._invoke(
            call,
            lambda next_call: self._transport.unary_unary(
                next_call.method,
                next_call.request,
                metadata=next_call.metadata,
                timeout=next_call.timeout,
            ),
        )

    async def call(
        self,
        method: str,
        request: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Execute a unary request-response call."""
        return await self.unary_unary(
            method,
            request,
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
        """Execute a unary request with a streaming response."""
        normalized_method, merged_metadata, resolved_timeout = self._prepare_call(
            method=method,
            metadata=metadata,
            timeout=timeout,
        )
        call = GrpcCall(
            method=normalized_method,
            request=request,
            metadata=merged_metadata,
            timeout=resolved_timeout,
        )
        return await self._invoke(
            call,
            lambda next_call: self._transport.unary_stream(
                next_call.method,
                next_call.request,
                metadata=next_call.metadata,
                timeout=next_call.timeout,
            ),
        )

    async def stream_unary(
        self,
        method: str,
        requests: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Execute a request stream with a unary response."""
        normalized_method, merged_metadata, resolved_timeout = self._prepare_call(
            method=method,
            metadata=metadata,
            timeout=timeout,
        )
        call = GrpcCall(
            method=normalized_method,
            request=requests,
            metadata=merged_metadata,
            timeout=resolved_timeout,
        )
        return await self._invoke(
            call,
            lambda next_call: self._transport.stream_unary(
                next_call.method,
                next_call.request,
                metadata=next_call.metadata,
                timeout=next_call.timeout,
            ),
        )

    async def stream_stream(
        self,
        method: str,
        requests: Any,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Execute a bidirectional streaming call."""
        normalized_method, merged_metadata, resolved_timeout = self._prepare_call(
            method=method,
            metadata=metadata,
            timeout=timeout,
        )
        call = GrpcCall(
            method=normalized_method,
            request=requests,
            metadata=merged_metadata,
            timeout=resolved_timeout,
        )
        return await self._invoke(
            call,
            lambda next_call: self._transport.stream_stream(
                next_call.method,
                next_call.request,
                metadata=next_call.metadata,
                timeout=next_call.timeout,
            ),
        )

    async def _invoke(self, call: GrpcCall, terminal: NextGrpcHandler) -> Any:
        """Execute one call through the interceptor chain.

        Interceptors are applied in declaration order so they compose like
        transport middleware: the first interceptor wraps all remaining work.
        """
        handler = terminal
        for interceptor in reversed(self._interceptors):
            next_handler = handler

            async def _wrapped(
                next_call: GrpcCall,
                *,
                _interceptor: AsyncGrpcInterceptor = interceptor,
                _next: NextGrpcHandler = next_handler,
            ) -> Any:
                return await _interceptor.handle(next_call, _next)

            handler = _wrapped

        return await handler(call)

    def _prepare_call(
        self,
        *,
        method: str,
        metadata: dict[str, str] | None,
        timeout: float | None,
    ) -> tuple[str, dict[str, str], float | None]:
        """Normalize method and resolve metadata and timeout."""
        normalized_method = self._normalize_method(method)
        merged_metadata = {**self._metadata, **(metadata or {})}
        resolved_timeout = self._timeout if timeout is None else timeout
        return normalized_method, merged_metadata, resolved_timeout

    @staticmethod
    def _normalize_method(method: str) -> str:
        """Normalize gRPC method path and reject empty names."""
        normalized = method.strip()
        if not normalized:
            raise ValueError("method must not be empty")
        if normalized.startswith("/"):
            return normalized
        return f"/{normalized}"
