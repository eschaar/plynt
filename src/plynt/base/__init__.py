"""Protocol-agnostic primitives for Plynt.

This package (``plynt.base``) contains all framework-agnostic, protocol-agnostic
primitives: data carriers, error types, protocols, and settings.

This is the foundation layer — nothing in ``plynt.base`` depends on HTTP,
frameworks, or optional extras.
"""

from plynt.base.cache import CacheBackend, SupportsSizeInfo, SupportsStats, SupportsTTL
from plynt.base.context import RequestIDPolicy, get_request_id
from plynt.base.errors import (
    AuthenticationError,
    BaseError,
    ConfigurationError,
    DependencyUnavailableError,
    FeatureDisabledError,
    InvalidInputError,
    OperationFailedError,
    StatusError,
    StreamInterruptedError,
    TransportConnectionError,
    TransportError,
    TransportTimeoutError,
)
from plynt.base.middleware import AsyncMiddleware, SyncMiddleware
from plynt.base.policies import CircuitBreakerPolicy, RateLimitPolicy, RetryPolicy
from plynt.base.request import Request
from plynt.base.response import (
    AsyncStreamingResponse,
    Response,
    ResponseProtocol,
    StreamingResponse,
)
from plynt.base.settings import Settings
from plynt.base.transport import (
    AsyncTransport,
    BaseAsyncTransport,
    BaseSyncTransport,
    SyncTransport,
)

__all__ = [
    "AsyncMiddleware",
    "AsyncStreamingResponse",
    "AsyncTransport",
    "AuthenticationError",
    "BaseAsyncTransport",
    "BaseError",
    "BaseSyncTransport",
    "CacheBackend",
    "CircuitBreakerPolicy",
    "ConfigurationError",
    "DependencyUnavailableError",
    "FeatureDisabledError",
    "InvalidInputError",
    "OperationFailedError",
    "RateLimitPolicy",
    "Request",
    "RequestIDPolicy",
    "Response",
    "ResponseProtocol",
    "RetryPolicy",
    "Settings",
    "StatusError",
    "StreamInterruptedError",
    "StreamingResponse",
    "SupportsSizeInfo",
    "SupportsStats",
    "SupportsTTL",
    "SyncMiddleware",
    "SyncTransport",
    "TransportConnectionError",
    "TransportError",
    "TransportTimeoutError",
    "get_request_id",
]
