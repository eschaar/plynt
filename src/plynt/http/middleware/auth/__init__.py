"""HTTP auth middleware for Plynt transports.

This package organises auth middleware by mechanism. All classes are
re-exported here for convenience.

Bearer token (``plynt.http.middleware.auth.bearer``):

- ``BearerTokenAuthMiddleware``
- ``AsyncBearerTokenAuthMiddleware``

Basic auth (``plynt.http.middleware.auth.basic``):

- ``BasicAuthMiddleware``
- ``AsyncBasicAuthMiddleware``

OAuth2 (``plynt.http.middleware.auth.oauth2``):

- ``OAuth2AuthMiddlewareBase`` / ``AsyncOAuth2AuthMiddlewareBase``
- ``OAuth2ClientCredentialsMiddleware`` / ``AsyncOAuth2ClientCredentialsMiddleware``
- ``OAuth2JWTBearerMiddleware`` / ``AsyncOAuth2JWTBearerMiddleware``
- ``OAuth2PasswordMiddleware`` / ``AsyncOAuth2PasswordMiddleware``
- ``OAuth2AuthMiddleware`` (alias) / ``AsyncOAuth2AuthMiddleware`` (alias)
"""

from plynt.http.middleware.auth.basic import (
    AsyncBasicAuthMiddleware,
    BasicAuthMiddleware,
)
from plynt.http.middleware.auth.bearer import (
    AsyncBearerTokenAuthMiddleware,
    BearerTokenAuthMiddleware,
)
from plynt.http.middleware.auth.oauth2 import (
    AsyncOAuth2AuthMiddleware,
    AsyncOAuth2AuthMiddlewareBase,
    AsyncOAuth2ClientCredentialsMiddleware,
    AsyncOAuth2JWTBearerMiddleware,
    AsyncOAuth2PasswordMiddleware,
    OAuth2AuthMiddleware,
    OAuth2AuthMiddlewareBase,
    OAuth2ClientCredentialsMiddleware,
    OAuth2JWTBearerMiddleware,
    OAuth2PasswordMiddleware,
)

__all__ = [
    "AsyncBasicAuthMiddleware",
    "AsyncBearerTokenAuthMiddleware",
    "AsyncOAuth2AuthMiddleware",
    "AsyncOAuth2AuthMiddlewareBase",
    "AsyncOAuth2ClientCredentialsMiddleware",
    "AsyncOAuth2JWTBearerMiddleware",
    "AsyncOAuth2PasswordMiddleware",
    "BasicAuthMiddleware",
    "BearerTokenAuthMiddleware",
    "OAuth2AuthMiddleware",
    "OAuth2AuthMiddlewareBase",
    "OAuth2ClientCredentialsMiddleware",
    "OAuth2JWTBearerMiddleware",
    "OAuth2PasswordMiddleware",
]
