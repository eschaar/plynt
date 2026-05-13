"""Typed authentication configuration for Plynth HTTP transports (ADR-0011).

Each supported auth mechanism has a corresponding config dataclass:

- ``BearerAuthConfig(token)`` — static bearer token / API key.
- ``BasicAuthConfig(username, password)`` — HTTP Basic authentication.
- ``OAuth2ClientCredentialsConfig(client_id, client_secret, token_url, ...)``
  — OAuth2 Client Credentials flow (machine-to-machine).
- ``OAuth2JWTBearerConfig(token_url, assertion_factory, cache_key_material, ...)``
    — OAuth2 JWT Bearer flow (RFC 7523).
- ``OAuth2PasswordConfig(client_id, client_secret, token_url, username,
  password, ...)`` — OAuth2 Resource Owner Password Credentials (legacy).

The union type alias ``AuthConfig`` covers all five.

Pass a config object to ``auth_from_config()`` (sync) or
``async_auth_from_config()`` (async) to obtain the corresponding
middleware instance.

**Usage pattern (ADR-0011):**

Declare secret values as pydantic env-var fields in your settings subclass,
then wire them into the config object inside the ``auth`` property:

Example::

    from plynth.http.auth import OAuth2ClientCredentialsConfig
    from plynth.http.settings import HTTPSettings
    from pydantic_settings import SettingsConfigDict

    class DataServiceSettings(HTTPSettings):
        model_config = SettingsConfigDict(
            env_prefix="DATA_",
            env_file=".env",
        )
        client_id:     str = ""  # DATA_CLIENT_ID=...
        client_secret: str = ""  # DATA_CLIENT_SECRET=...

        @property
        def auth(self):
            if not self.client_id:
                return None
            return OAuth2ClientCredentialsConfig(
                client_id=self.client_id,
                client_secret=self.client_secret,
                token_url="https://auth.example.com/oauth/token",
                ttl_leeway=60,
            )

    settings = DataServiceSettings()
    transport = HttpxSyncTransport.from_settings(settings)

JWT Bearer example::

    from plynth.http.auth import OAuth2JWTBearerConfig

    def build_assertion() -> str:
        return "<signed-jwt>"

    class JwtSettings(HTTPSettings):
        @property
        def auth(self):
            return OAuth2JWTBearerConfig(
                token_url="https://auth.example.com/oauth/token",
                assertion_factory=build_assertion,
                cache_key_material="issuer:service-account",
            )
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from plynth.base.middleware import AsyncMiddleware, SyncMiddleware

if TYPE_CHECKING:  # pragma: no cover
    from plynth.base.cache import CacheBackend
    from plynth.http.policies import HttpRetryPolicy

__all__ = [
    "AuthConfig",
    "BasicAuthConfig",
    "BearerAuthConfig",
    "OAuth2ClientCredentialsConfig",
    "OAuth2JWTBearerConfig",
    "OAuth2PasswordConfig",
    "async_auth_from_config",
    "auth_from_config",
]


JWTAssertionFactory = Callable[[], str]


@dataclass
class BearerAuthConfig:
    """Static bearer token / API key authentication.

    The token is attached as ``Authorization: Bearer <token>`` on every
    request.  A 401 response is never retried — static tokens cannot be
    refreshed.

    .. warning::
        Never hardcode the token.  Declare a pydantic field in your
        settings subclass and read it from an environment variable.

    Args:
        token: The bearer token string (without the ``Bearer `` prefix).

    Example::

        class MySettings(HTTPSettings):
            api_key: str = ""  # MY_API_KEY=...

            @property
            def auth(self) -> BearerAuthConfig | None:
                return BearerAuthConfig(token=self.api_key) if self.api_key else None

    """

    token: str


@dataclass
class BasicAuthConfig:
    """HTTP Basic authentication (username + password).

    Credentials are encoded once at construction time and reused for
    every request.  A 401 response is not retried — Basic credentials
    are static.

    .. warning::
        Never hardcode credentials.  Declare pydantic fields in your
        settings subclass and read them from environment variables.

    Example::

        class MySettings(HTTPSettings):
            api_user: str = ""  # MY_API_USER=...
            api_pass: str = ""  # MY_API_PASS=...

            @property
            def auth(self) -> BasicAuthConfig | None:
                if not self.api_user:
                    return None
                return BasicAuthConfig(username=self.api_user, password=self.api_pass)

    """

    username: str
    password: str


@dataclass
class OAuth2ClientCredentialsConfig:
    """OAuth2 Client Credentials flow (machine-to-machine).

    Fetches a bearer token using ``grant_type=client_credentials``.
    The token is cached (per-instance ``LocMemCache`` by default;
    override via the transport's ``default_auth_cache`` setting).
    A 401 response triggers one re-authentication attempt.

    Example::

        class SalesforceSettings(HTTPSettings):
            sf_client_id:     str = ""  # SF_CLIENT_ID=...
            sf_client_secret: str = ""  # SF_CLIENT_SECRET=...

            @property
            def auth(self) -> OAuth2ClientCredentialsConfig | None:
                if not self.sf_client_id:
                    return None
                return OAuth2ClientCredentialsConfig(
                    client_id=self.sf_client_id,
                    client_secret=self.sf_client_secret,
                    token_url="https://login.salesforce.com/services/oauth2/token",
                    ttl_leeway=60,
                )

    """

    client_id: str
    client_secret: str
    token_url: str
    token_retry_policy: HttpRetryPolicy | None = None
    ttl_leeway: int = 30


@dataclass
class OAuth2JWTBearerConfig:
    """OAuth2 JWT Bearer flow (RFC 7523).

    Fetches a bearer token using
    ``grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer`` and a
    signed JWT assertion generated by ``assertion_factory``.

    """

    token_url: str
    assertion_factory: JWTAssertionFactory
    cache_key_material: str
    scope: str | None = None
    token_retry_policy: HttpRetryPolicy | None = None
    ttl_leeway: int = 30


@dataclass
class OAuth2PasswordConfig:
    """OAuth2 Resource Owner Password Credentials flow (legacy).

    Fetches a bearer token using ``grant_type=password``.  Suitable only
    for trusted first-party applications.

    .. warning::
        The ROPC flow is considered legacy and is prohibited in OAuth 2.1.
        Prefer ``OAuth2ClientCredentialsConfig`` for machine-to-machine
        use cases.

    """

    client_id: str
    client_secret: str
    token_url: str
    username: str
    password: str
    token_retry_policy: HttpRetryPolicy | None = None
    ttl_leeway: int = 30


#: Union of all supported typed auth configuration objects.
#:
#: Pass one of these to ``auth_from_config()`` or
#: ``async_auth_from_config()`` to obtain a middleware instance, or
#: return it from the ``auth`` property on an ``HTTPSettings`` subclass.
AuthConfig = (
    BearerAuthConfig
    | BasicAuthConfig
    | OAuth2ClientCredentialsConfig
    | OAuth2JWTBearerConfig
    | OAuth2PasswordConfig
)


def auth_from_config(
    config: AuthConfig,
    token_cache: CacheBackend | None = None,
) -> SyncMiddleware:
    """Construct a sync auth middleware from a typed ``AuthConfig`` object.

    This is the preferred factory when using the typed configuration API
    (ADR-0011).  It constructs the appropriate middleware and wires all
    options declared on the config object.

    Supported config types:

    ===================================  =====================================
    Config type                          Middleware
    ===================================  =====================================
    ``BearerAuthConfig``                 ``BearerTokenAuthMiddleware``
    ``BasicAuthConfig``                  ``BasicAuthMiddleware``
    ``OAuth2ClientCredentialsConfig``    ``OAuth2ClientCredentialsMiddleware``
    ``OAuth2JWTBearerConfig``            ``OAuth2JWTBearerMiddleware``
    ``OAuth2PasswordConfig``             ``OAuth2PasswordMiddleware``
    ===================================  =====================================

    Args:
        config: A typed auth configuration object.
        token_cache: Optional ``CacheBackend`` for OAuth2 token caching.
            When ``None``, each middleware instance uses a private
            ``LocMemCache``.  Typically sourced from
            ``settings.caches[settings.default_auth_cache]`` (ADR-0010).

    """
    # Deferred imports — oauth2.py deferred-imports HttpxSyncTransport
    # inside __init__(), so importing middleware here does not cause a
    # circular import at module level.
    from plynth.http.middleware.auth import (
        BasicAuthMiddleware,
        BearerTokenAuthMiddleware,
        OAuth2ClientCredentialsMiddleware,
        OAuth2JWTBearerMiddleware,
        OAuth2PasswordMiddleware,
    )

    if isinstance(config, BearerAuthConfig):
        return BearerTokenAuthMiddleware(config.token)
    if isinstance(config, BasicAuthConfig):
        return BasicAuthMiddleware(config.username, config.password)
    if isinstance(config, OAuth2ClientCredentialsConfig):
        return OAuth2ClientCredentialsMiddleware(
            client_id=config.client_id,
            client_secret=config.client_secret,
            token_url=config.token_url,
            token_retry_policy=config.token_retry_policy,
            ttl_leeway=config.ttl_leeway,
            token_cache=token_cache,
        )
    if isinstance(config, OAuth2JWTBearerConfig):
        return OAuth2JWTBearerMiddleware(
            token_url=config.token_url,
            assertion_factory=config.assertion_factory,
            cache_key_material=config.cache_key_material,
            scope=config.scope,
            token_retry_policy=config.token_retry_policy,
            ttl_leeway=config.ttl_leeway,
            token_cache=token_cache,
        )
    # OAuth2PasswordConfig
    return OAuth2PasswordMiddleware(
        client_id=config.client_id,
        client_secret=config.client_secret,
        token_url=config.token_url,
        username=config.username,
        password=config.password,
        token_retry_policy=config.token_retry_policy,
        ttl_leeway=config.ttl_leeway,
        token_cache=token_cache,
    )


def async_auth_from_config(
    config: AuthConfig,
    token_cache: CacheBackend | None = None,
) -> AsyncMiddleware:
    """Construct an async auth middleware from a typed ``AuthConfig`` object.

    Async counterpart of ``auth_from_config()``.

    Args:
        config: A typed auth configuration object.
        token_cache: Optional ``CacheBackend`` for OAuth2 token caching.

    """
    from plynth.http.middleware.auth import (
        AsyncBasicAuthMiddleware,
        AsyncBearerTokenAuthMiddleware,
        AsyncOAuth2ClientCredentialsMiddleware,
        AsyncOAuth2JWTBearerMiddleware,
        AsyncOAuth2PasswordMiddleware,
    )

    if isinstance(config, BearerAuthConfig):
        return AsyncBearerTokenAuthMiddleware(config.token)
    if isinstance(config, BasicAuthConfig):
        return AsyncBasicAuthMiddleware(config.username, config.password)
    if isinstance(config, OAuth2ClientCredentialsConfig):
        return AsyncOAuth2ClientCredentialsMiddleware(
            client_id=config.client_id,
            client_secret=config.client_secret,
            token_url=config.token_url,
            token_retry_policy=config.token_retry_policy,
            ttl_leeway=config.ttl_leeway,
            token_cache=token_cache,
        )
    if isinstance(config, OAuth2JWTBearerConfig):
        return AsyncOAuth2JWTBearerMiddleware(
            token_url=config.token_url,
            assertion_factory=config.assertion_factory,
            cache_key_material=config.cache_key_material,
            scope=config.scope,
            token_retry_policy=config.token_retry_policy,
            ttl_leeway=config.ttl_leeway,
            token_cache=token_cache,
        )
    # OAuth2PasswordConfig
    return AsyncOAuth2PasswordMiddleware(
        client_id=config.client_id,
        client_secret=config.client_secret,
        token_url=config.token_url,
        username=config.username,
        password=config.password,
        token_retry_policy=config.token_retry_policy,
        ttl_leeway=config.ttl_leeway,
        token_cache=token_cache,
    )
