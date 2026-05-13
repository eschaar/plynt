"""HTTP transport layer: clients, request/response types, and transports."""

from plynth.http.client import APIClient, AsyncAPIClient, AsyncHTTPClient, HTTPClient
from plynth.http.errors import (
    BadRequestError,
    ConflictError,
    FeatureOfflineError,
    ForbiddenError,
    GoneError,
    HttpStatusError,
    InternalServerError,
    NotAllowedError,
    NotFoundError,
    OperationFailedError,
    RequestTimeoutError,
    ServiceUnavailableError,
    UnauthorizedError,
    UnprocessableEntityError,
    match_error,
)
from plynth.http.mapping import APIErrorMapper
from plynth.http.middleware.auth import (
    AsyncBasicAuthMiddleware,
    AsyncBearerTokenAuthMiddleware,
    AsyncOAuth2AuthMiddleware,
    AsyncOAuth2AuthMiddlewareBase,
    AsyncOAuth2ClientCredentialsMiddleware,
    AsyncOAuth2PasswordMiddleware,
    BasicAuthMiddleware,
    BearerTokenAuthMiddleware,
    OAuth2AuthMiddleware,
    OAuth2AuthMiddlewareBase,
    OAuth2ClientCredentialsMiddleware,
    OAuth2PasswordMiddleware,
)
from plynth.http.policies import HttpRetryPolicy
from plynth.http.renderer import JSONRenderer, Renderer
from plynth.http.response import HttpResponse
from plynth.http.service import (
    APIService,
    AsyncAPIService,
    AsyncHTTPService,
    HTTPService,
)
from plynth.http.settings import ApiSettings, HTTPSettings
from plynth.http.transport import HttpxAsyncTransport, HttpxSyncTransport

__all__ = [
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
