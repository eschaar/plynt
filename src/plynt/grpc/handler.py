"""Handler typing primitives for gRPC interceptor chains."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

__all__ = ["GrpcCall", "NextGrpcHandler"]


@dataclass(slots=True)
class GrpcCall:
    """Call envelope passed through interceptor chains."""

    method: str
    request: Any
    metadata: dict[str, str]
    timeout: float | None = None


NextGrpcHandler = Callable[["GrpcCall"], Awaitable[Any]]
