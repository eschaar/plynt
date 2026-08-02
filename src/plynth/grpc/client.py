"""Generic async-first gRPC client abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from plynth.grpc.settings import GrpcSettings

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
    ) -> None:
        """Initialize AsyncGrpcClient."""
        self._target = target
        self._transport = transport
        self._metadata = metadata or {}
        self._timeout = timeout

    @classmethod
    def from_settings(
        cls,
        settings: GrpcSettings,
        *,
        transport: AsyncGrpcTransport,
    ) -> AsyncGrpcClient:
        """Build a client from a ``GrpcSettings`` instance."""
        return cls(
            target=settings.target,
            transport=transport,
            metadata=settings.metadata,
            timeout=settings.timeout,
        )

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
        return await self._transport.unary_unary(
            normalized_method,
            request,
            metadata=merged_metadata,
            timeout=resolved_timeout,
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
        return await self._transport.unary_stream(
            normalized_method,
            request,
            metadata=merged_metadata,
            timeout=resolved_timeout,
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
        return await self._transport.stream_unary(
            normalized_method,
            requests,
            metadata=merged_metadata,
            timeout=resolved_timeout,
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
        return await self._transport.stream_stream(
            normalized_method,
            requests,
            metadata=merged_metadata,
            timeout=resolved_timeout,
        )

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
