"""Tests for public package exports in ``plynt.base``."""

import importlib

from plynt.base.cache import CacheBackend
from plynt.base.errors import BaseError, ConfigurationError
from plynt.base.middleware import AsyncMiddleware, SyncMiddleware
from plynt.base.request import Request
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

    def test_package_reexports_public_objects(self) -> None:
        """Verify package-level re-exports for base layer entry points."""
        module = importlib.import_module("plynt.base")

        assert module.AsyncMiddleware is AsyncMiddleware
        assert module.AsyncTransport is AsyncTransport
        assert module.BaseError is BaseError
        assert module.CacheBackend is CacheBackend
        assert module.ConfigurationError is ConfigurationError
        assert module.Request is Request
        assert module.Response is Response
        assert module.Settings is Settings
        assert module.SyncMiddleware is SyncMiddleware
        assert module.SyncTransport is SyncTransport
