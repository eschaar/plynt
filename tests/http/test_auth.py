"""Tests for plynth.http.auth — typed auth config dataclasses and factories."""

from __future__ import annotations

from plynth.http.auth import (
    BasicAuthConfig,
    BearerAuthConfig,
    OAuth2ClientCredentialsConfig,
    OAuth2JWTBearerConfig,
    OAuth2PasswordConfig,
    async_auth_from_config,
    auth_from_config,
)
from plynth.http.middleware.auth import (
    AsyncBasicAuthMiddleware,
    AsyncBearerTokenAuthMiddleware,
    AsyncOAuth2ClientCredentialsMiddleware,
    AsyncOAuth2JWTBearerMiddleware,
    AsyncOAuth2PasswordMiddleware,
    BasicAuthMiddleware,
    BearerTokenAuthMiddleware,
    OAuth2ClientCredentialsMiddleware,
    OAuth2JWTBearerMiddleware,
    OAuth2PasswordMiddleware,
)

_TOKEN = "my-bearer-token"
_USER = "my-user"
_PASS = "my-pass"
_CLIENT_ID = "client-id"
_CLIENT_SECRET = "client-secret"
_TOKEN_URL = "https://auth.example.com/token"


class TestBearerAuthConfig:
    """Test suite for BearerAuthConfig."""

    def test_fields(self) -> None:
        """Validate fields."""
        cfg = BearerAuthConfig(token=_TOKEN)
        assert cfg.token == _TOKEN

    def test_auth_from_config_returns_bearer_middleware(self) -> None:
        """Validate auth from config returns bearer middleware."""
        mw = auth_from_config(BearerAuthConfig(token=_TOKEN))
        assert isinstance(mw, BearerTokenAuthMiddleware)

    def test_async_auth_from_config_returns_async_bearer_middleware(self) -> None:
        """Validate async auth from config returns async bearer middleware."""
        mw = async_auth_from_config(BearerAuthConfig(token=_TOKEN))
        assert isinstance(mw, AsyncBearerTokenAuthMiddleware)


class TestBasicAuthConfig:
    """Test suite for BasicAuthConfig."""

    def test_fields(self) -> None:
        """Validate fields."""
        cfg = BasicAuthConfig(username=_USER, password=_PASS)
        assert cfg.username == _USER
        assert cfg.password == _PASS

    def test_auth_from_config_returns_basic_middleware(self) -> None:
        """Validate auth from config returns basic middleware."""
        mw = auth_from_config(BasicAuthConfig(username=_USER, password=_PASS))
        assert isinstance(mw, BasicAuthMiddleware)

    def test_async_auth_from_config_returns_async_basic_middleware(self) -> None:
        """Validate async auth from config returns async basic middleware."""
        mw = async_auth_from_config(BasicAuthConfig(username=_USER, password=_PASS))
        assert isinstance(mw, AsyncBasicAuthMiddleware)


class TestOAuth2ClientCredentialsConfig:
    """Test suite for OAuth2ClientCredentialsConfig."""

    def test_required_fields(self) -> None:
        """Validate required fields."""
        cfg = OAuth2ClientCredentialsConfig(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            token_url=_TOKEN_URL,
        )
        assert cfg.client_id == _CLIENT_ID
        assert cfg.client_secret == _CLIENT_SECRET
        assert cfg.token_url == _TOKEN_URL

    def test_default_values(self) -> None:
        """Validate default values."""
        cfg = OAuth2ClientCredentialsConfig(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            token_url=_TOKEN_URL,
        )
        assert cfg.token_retry_policy is None
        assert cfg.ttl_leeway == 30

    def test_custom_token_retry_policy(self) -> None:
        """Validate custom token retry policy."""
        from plynth.http.policies import HttpRetryPolicy

        policy = HttpRetryPolicy(max_attempts=5)
        cfg = OAuth2ClientCredentialsConfig(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            token_url=_TOKEN_URL,
            token_retry_policy=policy,
            ttl_leeway=60,
        )
        assert cfg.token_retry_policy is policy
        assert cfg.ttl_leeway == 60

    def test_auth_from_config_returns_oauth2_middleware(self) -> None:
        """Validate auth from config returns oauth2 middleware."""
        cfg = OAuth2ClientCredentialsConfig(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            token_url=_TOKEN_URL,
        )
        mw = auth_from_config(cfg)
        assert isinstance(mw, OAuth2ClientCredentialsMiddleware)

    def test_async_auth_from_config_returns_async_oauth2_middleware(self) -> None:
        """Validate async auth from config returns async oauth2 middleware."""
        cfg = OAuth2ClientCredentialsConfig(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            token_url=_TOKEN_URL,
        )
        mw = async_auth_from_config(cfg)
        assert isinstance(mw, AsyncOAuth2ClientCredentialsMiddleware)

    def test_auth_from_config_passes_options(self) -> None:
        """Validate auth from config passes options."""
        from http import HTTPStatus

        from plynth.http.policies import HttpRetryPolicy

        policy = HttpRetryPolicy(
            max_attempts=4,
            retryable_status_codes=frozenset({HTTPStatus.TOO_MANY_REQUESTS}),
        )
        cfg = OAuth2ClientCredentialsConfig(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            token_url=_TOKEN_URL,
            token_retry_policy=policy,
            ttl_leeway=45,
        )
        mw = auth_from_config(cfg)
        assert isinstance(mw, OAuth2ClientCredentialsMiddleware)
        assert mw._token_url == _TOKEN_URL
        assert mw._ttl_leeway == 45
        # token_retry_policy is wired into the internal transport.
        from plynth.http.transport import HttpxSyncTransport
        from plynth.middleware.retry import RetryMiddleware

        assert isinstance(mw._transport, HttpxSyncTransport)
        retry_mw = next(
            m for m in mw._transport._middlewares if isinstance(m, RetryMiddleware)
        )
        assert retry_mw._policy is policy


class TestOAuth2PasswordConfig:
    """Test suite for OAuth2PasswordConfig."""

    def test_required_fields(self) -> None:
        """Validate required fields."""
        cfg = OAuth2PasswordConfig(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            token_url=_TOKEN_URL,
            username=_USER,
            password=_PASS,
        )
        assert cfg.client_id == _CLIENT_ID
        assert cfg.username == _USER
        assert cfg.password == _PASS

    def test_default_values(self) -> None:
        """Validate default values."""
        cfg = OAuth2PasswordConfig(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            token_url=_TOKEN_URL,
            username=_USER,
            password=_PASS,
        )
        assert cfg.token_retry_policy is None
        assert cfg.ttl_leeway == 30

    def test_auth_from_config_returns_password_middleware(self) -> None:
        """Validate auth from config returns password middleware."""
        cfg = OAuth2PasswordConfig(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            token_url=_TOKEN_URL,
            username=_USER,
            password=_PASS,
        )
        mw = auth_from_config(cfg)
        assert isinstance(mw, OAuth2PasswordMiddleware)

    def test_async_auth_from_config_returns_async_password_middleware(self) -> None:
        """Validate async auth from config returns async password middleware."""
        cfg = OAuth2PasswordConfig(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            token_url=_TOKEN_URL,
            username=_USER,
            password=_PASS,
        )
        mw = async_auth_from_config(cfg)
        assert isinstance(mw, AsyncOAuth2PasswordMiddleware)


class TestOAuth2JWTBearerConfig:
    """Test suite for OAuth2JWTBearerConfig."""

    def test_required_fields(self) -> None:
        """Validate required fields."""
        cfg = OAuth2JWTBearerConfig(
            token_url=_TOKEN_URL,
            assertion_factory=lambda: "jwt.assertion",
            cache_key_material="issuer:user",
        )
        assert cfg.token_url == _TOKEN_URL
        assert cfg.cache_key_material == "issuer:user"

    def test_default_values(self) -> None:
        """Validate default values."""
        cfg = OAuth2JWTBearerConfig(
            token_url=_TOKEN_URL,
            assertion_factory=lambda: "jwt.assertion",
            cache_key_material="issuer:user",
        )
        assert cfg.scope is None
        assert cfg.token_retry_policy is None
        assert cfg.ttl_leeway == 30

    def test_auth_from_config_returns_jwt_bearer_middleware(self) -> None:
        """Validate sync factory returns JWT Bearer middleware."""
        cfg = OAuth2JWTBearerConfig(
            token_url=_TOKEN_URL,
            assertion_factory=lambda: "jwt.assertion",
            cache_key_material="issuer:user",
        )
        mw = auth_from_config(cfg)
        assert isinstance(mw, OAuth2JWTBearerMiddleware)

    def test_async_auth_from_config_returns_async_jwt_bearer_middleware(
        self,
    ) -> None:
        """Validate async factory returns JWT Bearer middleware."""
        cfg = OAuth2JWTBearerConfig(
            token_url=_TOKEN_URL,
            assertion_factory=lambda: "jwt.assertion",
            cache_key_material="issuer:user",
        )
        mw = async_auth_from_config(cfg)
        assert isinstance(mw, AsyncOAuth2JWTBearerMiddleware)


class TestAuthFromConfigWithTokenCache:
    """Verify that token_cache is forwarded to OAuth2 middlewares."""

    def test_token_cache_passed_to_oauth2_cc_middleware(self) -> None:
        """Validate token cache passed to oauth2 cc middleware."""
        from plynth.cache import LocMemCache

        cache = LocMemCache()
        cfg = OAuth2ClientCredentialsConfig(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            token_url=_TOKEN_URL,
        )
        mw = auth_from_config(cfg, token_cache=cache)
        assert isinstance(mw, OAuth2ClientCredentialsMiddleware)
        assert mw._cache is cache

    def test_token_cache_passed_to_async_oauth2_cc_middleware(self) -> None:
        """Validate token cache passed to async oauth2 cc middleware."""
        from plynth.cache import LocMemCache

        cache = LocMemCache()
        cfg = OAuth2ClientCredentialsConfig(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            token_url=_TOKEN_URL,
        )
        mw = async_auth_from_config(cfg, token_cache=cache)
        assert isinstance(mw, AsyncOAuth2ClientCredentialsMiddleware)
        assert mw._cache is cache

    def test_token_cache_none_by_default_bearer(self) -> None:
        """token_cache param is accepted but unused for bearer auth."""
        from plynth.cache import LocMemCache

        mw = auth_from_config(BearerAuthConfig(token=_TOKEN), token_cache=LocMemCache())
        assert isinstance(mw, BearerTokenAuthMiddleware)

    def test_token_cache_ignored_for_basic_auth(self) -> None:
        """token_cache param is accepted but unused for Basic auth."""
        from plynth.cache import LocMemCache

        mw = auth_from_config(
            BasicAuthConfig(username=_USER, password=_PASS),
            token_cache=LocMemCache(),
        )
        assert isinstance(mw, BasicAuthMiddleware)
