"""Tests for plynt.http.settings.HTTPSettings."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_settings import SettingsConfigDict

from plynt.base.settings import Settings
from plynt.cache import LocMemCacheConfig, RedisCacheConfig
from plynt.http.auth import (
    BasicAuthConfig,
    BearerAuthConfig,
    OAuth2ClientCredentialsConfig,
)
from plynt.http.settings import ApiSettings, HTTPSettings
from plynt.http.transport import HttpxSyncTransport
from plynt.middleware.retry import RetryMiddleware


class TestHTTPSettings:
    """Test suite for HTTPSettings."""

    def test_default_values(self) -> None:
        """Validate default values."""
        s = HTTPSettings()
        assert s.base_url == ""
        assert s.timeout_connect == 5.0
        assert s.timeout_read == 30.0
        assert s.timeout_write == 10.0
        assert s.timeout_pool == 10.0
        assert s.max_attempts == 3
        assert s.http2 is False
        assert s.trust_env is True
        assert s.max_redirects == 20
        assert s.max_connections is None
        assert s.max_keepalive_connections is None
        assert s.keepalive_expiry is None
        assert s.proxy is None
        assert s.verify is True
        assert s.cert is None
        assert s.debug is False
        # Auth and cache properties — all return None (disabled) by default.
        assert s.auth is None
        assert s.retry is None
        assert s.caches is None
        assert s.default_cache is None
        assert s.default_auth_cache is None

    def test_inherits_from_settings(self) -> None:
        """Validate inherits from settings."""
        assert issubclass(HTTPSettings, Settings)

    def test_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Validate loads from env."""
        monkeypatch.setenv("PLYNT_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("PLYNT_TIMEOUT_CONNECT", "3.0")
        monkeypatch.setenv("PLYNT_TIMEOUT_READ", "60.0")
        monkeypatch.setenv("PLYNT_TIMEOUT_WRITE", "20.0")
        monkeypatch.setenv("PLYNT_TIMEOUT_POOL", "15.0")
        monkeypatch.setenv("PLYNT_MAX_ATTEMPTS", "5")
        monkeypatch.setenv("PLYNT_HTTP2", "true")
        monkeypatch.setenv("PLYNT_TRUST_ENV", "false")
        monkeypatch.setenv("PLYNT_MAX_REDIRECTS", "8")
        monkeypatch.setenv("PLYNT_MAX_CONNECTIONS", "50")
        monkeypatch.setenv("PLYNT_MAX_KEEPALIVE_CONNECTIONS", "15")
        monkeypatch.setenv("PLYNT_KEEPALIVE_EXPIRY", "30.0")
        s = HTTPSettings()
        assert s.base_url == "https://api.example.com"
        assert s.timeout_connect == 3.0
        assert s.timeout_read == 60.0
        assert s.timeout_write == 20.0
        assert s.timeout_pool == 15.0
        assert s.max_attempts == 5
        assert s.http2 is True
        assert s.trust_env is False
        assert s.max_redirects == 8
        assert s.max_connections == 50
        assert s.max_keepalive_connections == 15
        assert s.keepalive_expiry == 30.0

    def test_is_subclassable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Validate is subclassable."""

        class MyServiceSettings(HTTPSettings):
            """Represent MyServiceSettings."""

            model_config = SettingsConfigDict(
                env_prefix="SVC_",
                env_file=".env",
            )

        monkeypatch.setenv("SVC_BASE_URL", "https://svc.example.com")
        s = MyServiceSettings()
        assert s.base_url == "https://svc.example.com"
        assert s.timeout_connect == 5.0

    def test_timeout_fields_accept_none(self) -> None:
        """Validate timeout fields accept none."""
        s = HTTPSettings(
            timeout_connect=None,
            timeout_read=None,
            timeout_write=None,
            timeout_pool=None,
        )
        assert s.timeout_connect is None
        assert s.timeout_read is None
        assert s.timeout_write is None
        assert s.timeout_pool is None

    def test_cache_backend_env_vars_are_not_parsed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Old string fields were removed; env vars no longer configure caches."""
        monkeypatch.setenv("PLYNT_CACHE_BACKEND", "locmem://default")
        monkeypatch.setenv("PLYNT_AUTH_CACHE_BACKEND", "redis://localhost:6379/0")
        s = HTTPSettings()
        # Properties return None — env vars have no effect on typed config.
        assert s.caches is None
        assert s.default_cache is None
        assert s.default_auth_cache is None


class TestHTTPSettingsCaches:
    """Tests for the typed cache configuration properties (ADR-0010)."""

    def test_caches_returns_none_by_default(self) -> None:
        """Validate caches returns none by default."""
        assert HTTPSettings().caches is None

    def test_default_cache_returns_none_by_default(self) -> None:
        """Validate default cache returns none by default."""
        assert HTTPSettings().default_cache is None

    def test_default_auth_cache_returns_none_by_default(self) -> None:
        """Validate default auth cache returns none by default."""
        assert HTTPSettings().default_auth_cache is None

    def test_subclass_can_override_caches(self) -> None:
        """Validate subclass can override caches."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def caches(self) -> dict[str, Any]:
                """Return caches."""
                return {"responses": LocMemCacheConfig()}

        s = _Settings()
        assert s.caches == {"responses": LocMemCacheConfig()}

    def test_subclass_can_override_default_cache(self) -> None:
        """Validate subclass can override default cache."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def default_cache(self) -> str:
                """Return default cache."""
                return "responses"

        assert _Settings().default_cache == "responses"

    def test_subclass_can_override_default_auth_cache(self) -> None:
        """Validate subclass can override default auth cache."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def default_auth_cache(self) -> str:
                """Return default auth cache."""
                return "tokens"

        assert _Settings().default_auth_cache == "tokens"

    def test_subclass_full_cache_configuration(self) -> None:
        """A fully configured subclass wires multiple named caches."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            redis_url: str = "redis://localhost:6379/0"

            @property
            def caches(self) -> dict[str, Any]:
                """Return caches."""
                return {
                    "responses": RedisCacheConfig(
                        location=self.redis_url,
                        key_prefix="svc:http:",
                    ),
                    "tokens": RedisCacheConfig(
                        location=self.redis_url,
                        key_prefix="svc:tokens:",
                        socket_timeout=1.0,
                    ),
                }

            @property
            def default_cache(self) -> str:
                """Return default cache."""
                return "responses"

            @property
            def default_auth_cache(self) -> str:
                """Return default auth cache."""
                return "tokens"

        s = _Settings()
        assert s.default_cache == "responses"
        assert s.default_auth_cache == "tokens"
        caches = s.caches
        assert caches is not None
        assert isinstance(caches["responses"], RedisCacheConfig)
        assert caches["responses"].key_prefix == "svc:http:"
        assert isinstance(caches["tokens"], RedisCacheConfig)
        assert caches["tokens"].socket_timeout == 1.0

    def test_caches_returns_none_when_url_not_configured(self) -> None:
        """Pattern: caches property returns None when the redis URL is empty."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            redis_url: str = ""

            @property
            def caches(self) -> dict[str, Any] | None:
                """Return caches."""
                if not self.redis_url:
                    return None
                return {
                    "responses": RedisCacheConfig(location=self.redis_url),
                }

        assert _Settings().caches is None


class TestHTTPSettingsAuth:
    """Tests for the typed auth configuration property (ADR-0011)."""

    def test_auth_returns_none_by_default(self) -> None:
        """Validate auth returns none by default."""
        assert HTTPSettings().auth is None

    def test_subclass_can_return_bearer_auth_config(self) -> None:
        """Validate subclass can return bearer auth config."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def auth(self) -> BearerAuthConfig:
                """Return auth."""
                return BearerAuthConfig(token="tok")

        assert _Settings().auth == BearerAuthConfig(token="tok")

    def test_subclass_can_return_oauth2_config(self) -> None:
        """Validate subclass can return oauth2 config."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def auth(self) -> OAuth2ClientCredentialsConfig:
                """Return auth."""
                return OAuth2ClientCredentialsConfig(
                    client_id="cid",
                    client_secret="sec",
                    token_url="https://auth.example.com/token",
                )

        cfg = _Settings().auth
        assert isinstance(cfg, OAuth2ClientCredentialsConfig)
        assert cfg.client_id == "cid"
        assert cfg.token_url == "https://auth.example.com/token"

    def test_subclass_can_return_basic_auth_config(self) -> None:
        """Validate subclass can return basic auth config."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def auth(self) -> BasicAuthConfig:
                """Return auth."""
                return BasicAuthConfig(username="user", password="pass")

        cfg = _Settings().auth
        assert isinstance(cfg, BasicAuthConfig)
        assert cfg.username == "user"

    def test_subclass_auth_returns_none_when_token_unset(self) -> None:
        """Pattern: guard on empty credential; returns None to disable auth."""

        class _Settings(HTTPSettings):
            """Represent Settings."""

            api_key: str = ""

            @property
            def auth(self) -> BearerAuthConfig | None:
                """Return auth."""
                return BearerAuthConfig(token=self.api_key) if self.api_key else None

        assert _Settings().auth is None
        assert _Settings(api_key="t").auth == BearerAuthConfig(token="t")


class TestApiSettings:
    """Test suite for ApiSettings."""

    def test_inherits_from_http_settings(self) -> None:
        """Validate inherits from http settings."""
        assert issubclass(ApiSettings, HTTPSettings)

    def test_default_values(self) -> None:
        """ApiSettings inherits all HTTPSettings fields including auth."""
        s = ApiSettings()
        assert s.base_url == ""
        assert s.timeout_connect == 5.0
        assert s.timeout_read == 30.0
        assert s.max_attempts == 3
        assert s.debug is False

    def test_loads_fields_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Validate loads fields from env."""
        monkeypatch.setenv("PLYNT_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("PLYNT_TIMEOUT_READ", "60.0")
        monkeypatch.setenv("PLYNT_DEBUG", "true")
        s = ApiSettings()
        assert s.base_url == "https://api.example.com"
        assert s.timeout_read == 60.0
        assert s.debug is True

    def test_is_subclassable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Validate is subclassable."""

        class CustomerServiceSettings(ApiSettings):
            """Represent CustomerServiceSettings."""

            model_config = SettingsConfigDict(
                env_prefix="CUSTOMER_",
                env_file=".env",
            )

        monkeypatch.setenv("CUSTOMER_BASE_URL", "https://customers.example.com")
        s = CustomerServiceSettings()
        assert s.base_url == "https://customers.example.com"
        assert s.timeout_connect == 5.0

    def test_build_transport_is_inherited(self) -> None:
        """from_settings() works on ApiSettings via HTTPSettings inheritance."""
        transport = HttpxSyncTransport.from_settings(ApiSettings())
        assert isinstance(transport, HttpxSyncTransport)
        # No auth configured: only RetryMiddleware is in the chain.
        assert len(transport._middlewares) == 1
        assert isinstance(transport._middlewares[0], RetryMiddleware)


class TestHTTPSettingsRetryProperty:
    """Tests for HTTPSettings.retry typed property (ADR-0012)."""

    def test_retry_returns_none_by_default(self) -> None:
        """Validate retry returns none by default."""
        assert HTTPSettings().retry is None

    def test_retry_can_be_overridden(self) -> None:
        """Validate retry can be overridden."""
        from plynt.http.policies import HttpRetryPolicy

        class _RetrySettings(HTTPSettings):
            """Represent RetrySettings."""

            @property
            def retry(self) -> HttpRetryPolicy:
                """Return retry."""
                return HttpRetryPolicy(
                    max_attempts=5,
                    backoff_initial=1.0,
                    retryable_status_codes=frozenset({429, 503}),
                )

        policy = _RetrySettings().retry
        assert policy is not None
        assert policy.max_attempts == 5
        assert policy.backoff_initial == 1.0
        assert policy.retryable_status_codes == frozenset({429, 503})
