"""HTTP transport and REST API settings for Plynth.

Extends ``plynth.base.settings.Settings`` with fields that control HTTP
transport behaviour: base URL, timeouts, retry, proxy, TLS, and
authentication. This is the middle layer in the three-layer settings
hierarchy (ADR-0004):

- ``plynth.base.settings.Settings`` — universal base (debug + .env)
- ``plynth.http.settings.HTTPSettings`` — this class
- ``plynth.http.settings.ApiSettings`` — thin subclass for REST API clients

Authentication is an HTTP-level concern and is configured via a typed
config object (ADR-0011).  Override the ``auth`` property in a subclass
to enable auth.  Pass the settings instance to
``HttpxSyncTransport.from_settings()`` to get a fully configured
transport with auth wired automatically.

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
            )

Caching (ADR-0010)
-------------------

Cache backends are configured by overriding the ``caches``,
``default_cache``, and ``default_auth_cache`` properties in a subclass:

- ``caches`` — returns a ``dict[str, CacheConfig]`` mapping cache names
  to typed configuration objects, or ``None`` to disable caching.
- ``default_cache`` — key in ``caches`` to use for HTTP response caching.
- ``default_auth_cache`` — key in ``caches`` for the OAuth2 token cache.

Example::

    from plynth.cache import RedisCacheConfig
    from plynth.http.settings import HTTPSettings
    from pydantic_settings import SettingsConfigDict

    class DataServiceSettings(HTTPSettings):
        model_config = SettingsConfigDict(
            env_prefix="DATA_",
            env_file=".env",
        )
        redis_url: str = ""  # DATA_REDIS_URL=redis://...

        @property
        def caches(self):
            if not self.redis_url:
                return None
            return {
                "responses": RedisCacheConfig(
                    location=self.redis_url,
                    key_prefix="data:http:",
                ),
            }

        @property
        def default_cache(self):
            return "responses"

    settings = DataServiceSettings()
    transport = HttpxSyncTransport.from_settings(settings)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_settings import SettingsConfigDict

from plynth.base.settings import Settings

if TYPE_CHECKING:  # pragma: no cover
    from plynth.cache import CacheConfig
    from plynth.http.auth import AuthConfig
    from plynth.http.policies import HttpRetryPolicy

__all__ = ["ApiSettings", "HTTPSettings"]


class HTTPSettings(Settings):
    """Settings for an HTTP transport with optional authentication.

    Provides all fields needed to build and configure an
    ``HttpxSyncTransport`` or ``HttpxAsyncTransport``.

    Attributes:
        base_url: Base URL of the external service (default: ``""``).
        timeout_connect: Seconds to wait for a connection to be
            established (default: ``5.0``). ``None`` disables the limit.
        timeout_read: Seconds to wait for data to be received from the
            server (default: ``30.0``). ``None`` disables the limit.
        timeout_write: Seconds to wait for data to be sent to the server
            (default: ``10.0``). ``None`` disables the limit.
        timeout_pool: Seconds to wait for a free connection from the
            connection pool (default: ``10.0``). ``None`` disables the
            limit.
        max_attempts: Total send attempts including the first
            (default: ``3``).
        proxy: Optional proxy URL.
        verify: SSL certificate verification. ``True`` uses system CAs,
            ``False`` disables, or a path to a CA bundle.
        cert: Client certificate — PEM path or ``(cert, key)`` tuple.

    Properties (override in subclasses):
        auth: Typed auth configuration (ADR-0011). Return an
            ``AuthConfig`` instance to enable authentication, or
            ``None`` to disable (default).  Declare credential fields
            (tokens, passwords) as pydantic env-var fields on the
            subclass and construct the config here.
        caches: A mapping of cache names to ``CacheConfig`` objects, or
            ``None`` to disable caching entirely (default: ``None``).
        default_cache: Name of the entry in ``caches`` to use for HTTP
            response caching (default: ``None``).
        default_auth_cache: Name of the entry in ``caches`` to use for
            the OAuth2 token cache (default: ``None``).

    Example::

        from plynth.http.auth import OAuth2ClientCredentialsConfig

        class OrderServiceSettings(HTTPSettings):
            model_config = SettingsConfigDict(
                env_prefix="ORDER_",
                env_file=".env",
            )
            client_id:     str = ""  # ORDER_CLIENT_ID=...
            client_secret: str = ""  # ORDER_CLIENT_SECRET=...

            @property
            def auth(self):
                if not self.client_id:
                    return None
                return OAuth2ClientCredentialsConfig(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    token_url="https://auth.example.com/token",
                )

        settings = OrderServiceSettings()
        transport = HttpxSyncTransport.from_settings(settings)

    """

    base_url: str = ""
    timeout_connect: float | None = 5.0
    timeout_read: float | None = 30.0
    timeout_write: float | None = 10.0
    timeout_pool: float | None = 10.0
    max_attempts: int = 3
    proxy: str | None = None
    verify: bool | str = True
    cert: tuple[str, str] | str | None = None

    model_config = SettingsConfigDict(
        env_prefix="PLYNTH_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def auth(self) -> AuthConfig | None:
        """Typed auth configuration (ADR-0011).

        Override in a subclass to enable authentication.  Declare secret
        values (tokens, passwords) as pydantic fields on the subclass and
        construct the config object here:

        Example::

            from plynth.http.auth import BearerAuthConfig

            class MySettings(HTTPSettings):
                api_key: str = ""  # MY_API_KEY=...

                @property
                def auth(self) -> BearerAuthConfig | None:
                    return (
                        BearerAuthConfig(token=self.api_key) if self.api_key else None
                    )

        Returns:
            An ``AuthConfig`` instance, or ``None`` to disable auth
            (default).

        """
        return None

    @property
    def retry(self) -> HttpRetryPolicy | None:
        """Typed retry policy (ADR-0012).

        Override in a subclass to control backoff, retryable status codes,
        and attempt limits via a fully configured ``HttpRetryPolicy``.
        When this returns ``None`` (default), ``from_settings()`` falls
        back to ``HttpRetryPolicy(max_attempts=self.max_attempts)``.

        Example::

            from http import HTTPStatus
            from plynth.http.policies import HttpRetryPolicy
            from plynth.http.settings import HTTPSettings

            class MySettings(HTTPSettings):
                @property
                def retry(self) -> HttpRetryPolicy:
                    return HttpRetryPolicy(
                        max_attempts=5,
                        backoff_initial=1.0,
                        # Replaces the defaults — include every code
                        # you want to retry.
                        retryable_status_codes=frozenset({
                            HTTPStatus.TOO_MANY_REQUESTS,
                            HTTPStatus.SERVICE_UNAVAILABLE,
                        }),
                    )

        Returns:
            An ``HttpRetryPolicy`` instance, or ``None`` to use the
            ``max_attempts`` fallback (default).

        """
        return None

    @property
    def caches(self) -> dict[str, CacheConfig] | None:
        """Named cache configurations.

        Override in a subclass to enable caching.  Each value is a
        ``CacheConfig`` dataclass (``LocMemCacheConfig``,
        ``RedisCacheConfig``, or ``DummyCacheConfig``).  Keys are
        arbitrary names referenced by ``default_cache`` and
        ``default_auth_cache``.

        Returns ``None`` by default, meaning no caching is configured.

        """
        return None

    @property
    def default_cache(self) -> str | None:
        """Name of the cache (from ``caches``) used for HTTP response caching.

        Returns ``None`` by default, meaning response caching is
        disabled.

        """
        return None

    @property
    def default_auth_cache(self) -> str | None:
        """Name of the cache (from ``caches``) used for OAuth2 token caching.

        Returns ``None`` by default, meaning each transport instance
        uses its own private in-process token cache.

        """
        return None


class ApiSettings(HTTPSettings):
    """Thin subclass of ``HTTPSettings`` for REST API clients.

    Currently adds no new fields. Subclass this to keep your code
    forward-compatible with future REST-specific settings.
    """
