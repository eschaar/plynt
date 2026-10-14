"""gRPC-specific transport errors."""

from __future__ import annotations

from typing import Any

from plynt.base.errors import StatusError, TransportError

__all__ = ["GrpcStatusError", "GrpcTransportError", "StatusError", "TransportError"]


class GrpcTransportError(TransportError):
    """Raised when a gRPC transport call fails before a status is returned."""

    code = "GRPC_TRANSPORT_ERROR"
    message = "A gRPC transport error occurred"


class GrpcStatusError(StatusError):
    """Raised when a gRPC status code indicates a failed call."""

    code = "GRPC_STATUS_ERROR"
    message = "gRPC status indicates failure"

    def __init__(
        self,
        message: str | None = None,
        *,
        status_code: int,
        method: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize GrpcStatusError."""
        super().__init__(message, status_code=status_code, method=method, **kwargs)
        self.method = method
