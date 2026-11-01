"""Tests for public package exports in ``plynt.base``."""

import importlib

from plynt.base.cache import CacheBackend
from plynt.base.error_envelope import (
    ErrorEnvelope,
    build_error_envelope,
    default_error_envelope,
)
from plynt.base.errors import (
    AuthenticationError,
    BaseError,
    ConfigurationError,
    TransportConnectionError,
    TransportTimeoutError,
)
from plynt.base.middleware import AsyncMiddleware, SyncMiddleware
from plynt.base.request import Request
from plynt.base.request_id import RequestIDPolicy, get_request_id
from plynt.base.response import Response
from plynt.base.settings import Settings
from plynt.base.transport import AsyncTransport, SyncTransport


class TestBasePackage:
    """Verify package-level exports and import behavior."""

    def test_package_exports_public_names(self) -> None:
        """Verify the stable public names exported by the package."""
        module = importlib.import_module("plynt.base")

        assert module.__all__ == [
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
            "ErrorEnvelope",
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
            "build_error_envelope",
            "default_error_envelope",
            "get_request_id",
        ]

    def test_package_reexports_public_objects(self) -> None:
        """Verify package-level re-exports for base layer entry points."""
        module = importlib.import_module("plynt.base")

        assert module.AsyncMiddleware is AsyncMiddleware
        assert module.AsyncTransport is AsyncTransport
        assert module.AuthenticationError is AuthenticationError
        assert module.BaseError is BaseError
        assert module.CacheBackend is CacheBackend
        assert module.ConfigurationError is ConfigurationError
        assert module.ErrorEnvelope is ErrorEnvelope
        assert module.build_error_envelope is build_error_envelope
        assert module.default_error_envelope is default_error_envelope
        assert module.Request is Request
        assert module.RequestIDPolicy is RequestIDPolicy
        assert module.get_request_id is get_request_id
        assert module.Response is Response
        assert module.Settings is Settings
        assert module.SyncMiddleware is SyncMiddleware
        assert module.SyncTransport is SyncTransport
        assert module.TransportConnectionError is TransportConnectionError
        assert module.TransportTimeoutError is TransportTimeoutError
