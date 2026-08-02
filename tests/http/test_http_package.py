"""Tests for public package exports in ``plynth.http``."""

import importlib

from plynth.http.client import APIClient, HTTPClient
from plynth.http.errors import HttpStatusError, match_error
from plynth.http.mapping import APIErrorMapper
from plynth.http.service import APIService, HTTPService
from plynth.http.settings import HTTPSettings
from plynth.http.transport import HttpxAsyncTransport, HttpxSyncTransport


class TestHttpPackage:
    """Verify package-level exports and import behavior."""

    def test_package_exports_public_names(self) -> None:
        """Verify the stable public names exported by the package."""
        module = importlib.import_module("plynth.http")

        assert module.__all__ == [
            "APIClient",
            "APIErrorMapper",
            "APIService",
            "ApiSettings",
            "AsyncAPIClient",
            "AsyncAPIService",
            "AsyncBasicAuthMiddleware",
            "AsyncBearerTokenAuthMiddleware",
            "AsyncHTTPClient",
            "AsyncHTTPService",
            "AsyncOAuth2AuthMiddleware",
            "AsyncOAuth2AuthMiddlewareBase",
            "AsyncOAuth2ClientCredentialsMiddleware",
            "AsyncOAuth2PasswordMiddleware",
            "BadRequestError",
            "BasicAuthMiddleware",
            "BearerTokenAuthMiddleware",
            "ConflictError",
            "FeatureOfflineError",
            "ForbiddenError",
            "GoneError",
            "HTTPClient",
            "HTTPService",
            "HTTPSettings",
            "HttpResponse",
            "HttpRetryPolicy",
            "HttpStatusError",
            "HttpxAsyncTransport",
            "HttpxSyncTransport",
            "InternalServerError",
            "JSONRenderer",
            "NotAllowedError",
            "NotFoundError",
            "OAuth2AuthMiddleware",
            "OAuth2AuthMiddlewareBase",
            "OAuth2ClientCredentialsMiddleware",
            "OAuth2PasswordMiddleware",
            "OperationFailedError",
            "Renderer",
            "RequestTimeoutError",
            "ServiceUnavailableError",
            "UnauthorizedError",
            "UnprocessableEntityError",
            "match_error",
        ]

    def test_package_reexports_public_objects(self) -> None:
        """Verify package-level re-exports for HTTP layer entry points."""
        module = importlib.import_module("plynth.http")

        assert module.APIClient is APIClient
        assert module.APIErrorMapper is APIErrorMapper
        assert module.APIService is APIService
        assert module.HTTPClient is HTTPClient
        assert module.HTTPService is HTTPService
        assert module.HTTPSettings is HTTPSettings
        assert module.HttpStatusError is HttpStatusError
        assert module.HttpxAsyncTransport is HttpxAsyncTransport
        assert module.HttpxSyncTransport is HttpxSyncTransport
        assert module.match_error is match_error
