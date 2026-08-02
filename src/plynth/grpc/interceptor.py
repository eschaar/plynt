"""Interceptor protocol primitives for gRPC client calls."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

__all__ = ["AsyncGrpcInterceptor", "GrpcCall", "NextGrpcHandler"]


@dataclass(slots=True)
class GrpcCall:
    """Call envelope passed through interceptor chains."""

    method: str
    request: Any
    metadata: dict[str, str]
    timeout: float | None = None


NextGrpcHandler = Callable[[GrpcCall], Awaitable[Any]]


@runtime_checkable
class AsyncGrpcInterceptor(Protocol):
    """Protocol for asynchronous gRPC interceptors."""

    async def handle(self, call: GrpcCall, next_handler: NextGrpcHandler) -> Any:
        """Process a call and return the downstream response."""
        raise NotImplementedError
