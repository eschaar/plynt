"""Protocol-agnostic primitives for Plynt.

This package (``plynt.base``) contains all framework-agnostic, protocol-agnostic
primitives: data carriers, error types, protocols, and settings.

This is the foundation layer — nothing in ``plynt.base`` depends on HTTP,
frameworks, or optional extras.
"""

from plynt.base.cache import CacheBackend, SupportsSizeInfo, SupportsStats, SupportsTTL
from plynt.base.errors import (
    BaseError,
    ConfigurationError,
    DependencyUnavailableError,
    FeatureDisabledError,
    InvalidInputError,
    OperationFailedError,
    StatusError,
    StreamInterruptedError,
    TransportError,
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
    "TransportError",
]
