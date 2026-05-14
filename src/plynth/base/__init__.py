"""Protocol-agnostic primitives for Plynth.

This package (``plynth.base``) contains all framework-agnostic, protocol-agnostic
primitives: data carriers, error types, protocols, and settings.

This is the foundation layer — nothing in ``plynth.base`` depends on HTTP,
frameworks, or optional extras.
"""

from plynth.base.cache import CacheBackend, SupportsSizeInfo, SupportsStats, SupportsTTL
from plynth.base.errors import (
    BaseError,
    ConfigurationError,
    DependencyUnavailableError,
    FeatureDisabledError,
    InvalidInputError,
    OperationFailedError,
    StatusError,
    TransportError,
)
from plynth.base.middleware import AsyncMiddleware, SyncMiddleware
from plynth.base.policies import RetryPolicy
from plynth.base.request import Request
from plynth.base.response import (
    AsyncStreamingResponse,
    Response,
    ResponseProtocol,
    StreamingResponse,
)
from plynth.base.settings import Settings
from plynth.base.transport import (
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
    "ConfigurationError",
    "DependencyUnavailableError",
    "FeatureDisabledError",
    "InvalidInputError",
    "OperationFailedError",
    "Request",
    "Response",
    "ResponseProtocol",
    "RetryPolicy",
    "Settings",
    "StatusError",
    "StreamingResponse",
    "SupportsSizeInfo",
    "SupportsStats",
    "SupportsTTL",
    "SyncMiddleware",
    "SyncTransport",
    "TransportError",
]
