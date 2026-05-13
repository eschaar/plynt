"""HTTP-specific middleware for Plynth transports.

This subpackage contains HTTP-protocol-specific middleware:

- ``plynth.http.middleware.auth`` — bearer, basic, and OAuth2 auth
  middleware (sync and async). Includes abstract OAuth2 bases and
  concrete flow implementations (Client Credentials, Password).

``HttpRetryPolicy`` lives in ``plynth.http.policies``, not here.
"""

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

__all__ = [
    "AsyncBasicAuthMiddleware",
    "AsyncBearerTokenAuthMiddleware",
    "AsyncOAuth2AuthMiddleware",
    "AsyncOAuth2AuthMiddlewareBase",
    "AsyncOAuth2ClientCredentialsMiddleware",
    "AsyncOAuth2PasswordMiddleware",
    "BasicAuthMiddleware",
    "BearerTokenAuthMiddleware",
    "OAuth2AuthMiddleware",
    "OAuth2AuthMiddlewareBase",
    "OAuth2ClientCredentialsMiddleware",
    "OAuth2PasswordMiddleware",
]
