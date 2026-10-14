"""HTTP transport layer: clients, request/response types, and transports."""

from plynt.http.client import APIClient, AsyncAPIClient, AsyncHTTPClient, HTTPClient
from plynt.http.errors import (
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
from plynt.http.mapping import APIErrorMapper
from plynt.http.middleware.auth import (
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
from plynt.http.policies import HttpRetryPolicy
from plynt.http.renderer import JSONRenderer, Renderer
from plynt.http.response import HttpResponse
from plynt.http.service import (
    APIService,
    AsyncAPIService,
    AsyncHTTPService,
    HTTPService,
)
from plynt.http.settings import ApiSettings, HTTPSettings
from plynt.http.transport import HttpxAsyncTransport, HttpxSyncTransport

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
