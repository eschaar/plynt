"""Interceptor protocol primitives for gRPC client calls."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from plynt.grpc.handler import GrpcCall, NextGrpcHandler

__all__ = ["AsyncGrpcInterceptor", "GrpcCall", "NextGrpcHandler"]


@runtime_checkable
class AsyncGrpcInterceptor(Protocol):
    """Protocol for asynchronous gRPC interceptors."""

    async def handle(self, call: GrpcCall, next_handler: NextGrpcHandler) -> Any:
        """Process a call and return the downstream response."""
        raise NotImplementedError
