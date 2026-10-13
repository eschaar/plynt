"""Tests for public package exports in ``plynth.base``."""

import importlib

from plynth.base.cache import CacheBackend
from plynth.base.errors import BaseError, ConfigurationError
from plynth.base.middleware import AsyncMiddleware, SyncMiddleware
from plynth.base.request import Request
from plynth.base.response import Response
from plynth.base.settings import Settings
from plynth.base.transport import AsyncTransport, SyncTransport


class TestBasePackage:
    """Verify package-level exports and import behavior."""

    def test_package_exports_public_names(self) -> None:
        """Verify the stable public names exported by the package."""
        module = importlib.import_module("plynth.base")

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
        module = importlib.import_module("plynth.base")

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
