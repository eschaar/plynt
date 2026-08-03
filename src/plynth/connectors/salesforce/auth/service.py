"""Salesforce OAuth2 auth middleware for Plynth.

Extends ``OAuth2AuthMiddleware`` to also capture and cache the
``instance_url`` returned in the Salesforce token response. The instance URL
is the org-specific host used as the base URL for all Salesforce REST API
calls, and must be used instead of the generic ``login.salesforce.com`` host.

Because Salesforce may assign different ``instance_url`` values to the same
connected app over time (e.g. after a sandbox refresh or org migration),
``instance_url`` is cached alongside the access token and invalidated together
with it — so the client always uses the URL Salesforce assigned with the most
recently issued token.

Usage::

    from plynth.http.transport import HttpxSyncTransport
    from plynth.connectors.salesforce.auth import (
        SalesforceClientCredentialsAuthMiddleware,
    )
    from plynth.connectors.salesforce.client import SalesforceAPIClient

    auth = SalesforceClientCredentialsAuthMiddleware(
        client_id="3MVG9...",
        client_secret="abc123",
        token_url="https://login.salesforce.com/services/oauth2/token",
    )
    transport = HttpxSyncTransport(middlewares=[auth])
    client = SalesforceAPIClient(auth=auth, transport=transport)

"""

from __future__ import annotations

import time
from typing import Any, cast
from urllib.parse import urlsplit

from plynth.http.middleware.auth import (
    AsyncBearerTokenAuthMiddleware,
    AsyncOAuth2ClientCredentialsMiddleware,
    AsyncOAuth2JWTBearerMiddleware,
    AsyncOAuth2PasswordMiddleware,
    BearerTokenAuthMiddleware,
    OAuth2ClientCredentialsMiddleware,
    OAuth2JWTBearerMiddleware,
    OAuth2PasswordMiddleware,
)

pyjwt: Any | None

try:
    import jwt as pyjwt
except ImportError:
    pyjwt = None

__all__ = [
    "AsyncSalesforceClientCredentialsAuthMiddleware",
    "AsyncSalesforceJWTBearerAuthMiddleware",
    "AsyncSalesforceOAuth2AuthMiddleware",
    "AsyncSalesforcePasswordAuthMiddleware",
    "AsyncSalesforceSessionAuthMiddleware",
    "SalesforceClientCredentialsAuthMiddleware",
    "SalesforceJWTBearerAuthMiddleware",
    "SalesforceOAuth2AuthMiddleware",
    "SalesforcePasswordAuthMiddleware",
    "SalesforceSessionAuthMiddleware",
]


class SalesforceSessionAuthMiddleware(BearerTokenAuthMiddleware):
    """Attach an externally managed Salesforce access token to requests.

    Use this middleware when your application lifecycle already handles token
    acquisition and refresh, and only needs Plynth to inject the bearer token
    and route calls to the right Salesforce ``instance_url``.
    """

    def __init__(self, *, access_token: str, instance_url: str) -> None:
        """Initialize SalesforceSessionAuthMiddleware."""
        super().__init__(access_token)
        self._instance_url = instance_url.rstrip("/")

    @property
    def instance_url(self) -> str:
        """Return the Salesforce instance URL for the current session token."""
        return self._instance_url


class AsyncSalesforceSessionAuthMiddleware(AsyncBearerTokenAuthMiddleware):
    """Async middleware for externally managed Salesforce session tokens."""

    def __init__(self, *, access_token: str, instance_url: str) -> None:
        """Initialize AsyncSalesforceSessionAuthMiddleware."""
        super().__init__(access_token)
        self._instance_url = instance_url.rstrip("/")

    async def get_instance_url(self) -> str:
        """Return the Salesforce instance URL for the current session token."""
        return self._instance_url


# pylint: disable=too-few-public-methods
class _SalesforceInstanceUrlSyncMixin:
    """Shared Salesforce ``instance_url`` behavior for sync OAuth2 middlewares."""

    _lock: Any
    _cache: Any
    _cache_key: str
    _fetch: Any

    def __init__(self, **kwargs: Any) -> None:
        """Initialize _SalesforceInstanceUrlSyncMixin."""
        super().__init__(**kwargs)
        self._instance_url: str | None = None

    @property
    def instance_url(self) -> str:
        """Return the Salesforce instance URL, fetching a token first if needed.

        Triggers a token fetch (and caches the result) if no valid token is
        cached. Thread-safe: shares the parent's lock.

        Returns:
            The org-specific Salesforce host (e.g.
            ``"https://myorg.my.salesforce.com"``).

        Raises:
            RuntimeError: If the token endpoint response did not include an
                ``instance_url`` field.

        """
        with self._lock:
            entry = self._cache.get(self._cache_key)
            if entry is None or time.monotonic() >= entry[1]:
                self._fetch()
            if self._instance_url is None:  # pragma: no cover
                raise RuntimeError(
                    "Token fetched but 'instance_url' was not set. "
                    "Check that _on_response ran successfully."
                )
        return self._instance_url

    def _extract_instance_url(self, data: dict[str, Any]) -> str:
        """Return ``instance_url`` from the token response, raising if absent."""
        instance_url = data.get("instance_url")
        if not isinstance(instance_url, str) or not instance_url:
            raise RuntimeError(
                "Salesforce token response did not include 'instance_url'. "
                "Ensure the connected app/token endpoint returns this field."
            )
        return instance_url


# pylint: disable=too-few-public-methods
class _SalesforceInstanceUrlAsyncMixin:
    """Shared Salesforce ``instance_url`` behavior for async OAuth2 middlewares."""

    _lock: Any
    _cache: Any
    _cache_key: str
    _fetch: Any

    def __init__(self, **kwargs: Any) -> None:
        """Initialize _SalesforceInstanceUrlAsyncMixin."""
        super().__init__(**kwargs)
        self._instance_url: str | None = None

    async def get_instance_url(self) -> str:
        """Return the Salesforce instance URL, fetching a token first if needed.

        Triggers a token fetch (and caches the result) if no valid token is
        cached. Concurrency-safe: shares the parent's asyncio lock.

        Returns:
            The org-specific Salesforce host (e.g.
            ``"https://myorg.my.salesforce.com"``).

        Raises:
            RuntimeError: If the token endpoint response did not include an
                ``instance_url`` field.

        """
        async with self._lock:
            entry = self._cache.get(self._cache_key)
            if entry is None or time.monotonic() >= entry[1]:
                await self._fetch()
            if self._instance_url is None:  # pragma: no cover
                raise RuntimeError(
                    "Token fetched but 'instance_url' was not set. "
                    "Check that _on_response ran successfully."
                )
        return self._instance_url

    def _extract_instance_url(self, data: dict[str, Any]) -> str:
        """Return ``instance_url`` from the token response, raising if absent."""
        instance_url = data.get("instance_url")
        if not isinstance(instance_url, str) or not instance_url:
            raise RuntimeError(
                "Salesforce token response did not include 'instance_url'. "
                "Ensure the connected app/token endpoint returns this field."
            )
        return instance_url


class SalesforceClientCredentialsAuthMiddleware(
    _SalesforceInstanceUrlSyncMixin,
    OAuth2ClientCredentialsMiddleware,
):
    """OAuth2 auth middleware for the Salesforce Platform API.

    Extends ``OAuth2AuthMiddleware`` to extract and cache the
    ``instance_url`` field from the Salesforce token response. The instance
    URL identifies the org-specific Salesforce host (e.g.
    ``"https://myorg.my.salesforce.com"``) and is required as the base URL
    for all REST API calls.

    ``instance_url`` and the access token share the same expiry and lock, so
    both are always in sync. Calling ``_invalidate()`` causes both to be
    re-fetched on the next request.
    """

    def _on_response(self, data: dict[str, Any]) -> None:
        """Extract and cache instance_url alongside the access token."""
        instance_url = self._extract_instance_url(data)
        super()._on_response(data)
        self._instance_url = instance_url


class SalesforcePasswordAuthMiddleware(
    _SalesforceInstanceUrlSyncMixin,
    OAuth2PasswordMiddleware,
):
    """Salesforce OAuth2 Password middleware with cached ``instance_url``.

    Use this middleware for the OAuth2 Resource Owner Password Credentials
    flow. The middleware captures and caches ``instance_url`` alongside the
    access token, so ``SalesforceAPIClient`` can always target the current
    org-specific host.

    When a ``security_token`` is provided it is automatically appended to
    the password before the token request — matching Salesforce's requirement
    for orgs without IP allowlisting.

    Args:
        security_token: Optional Salesforce security token. When supplied,
            it is appended to ``password`` before the token request. Leave
            empty for orgs with IP allowlisting.

    """

    def __init__(
        self,
        *,
        password: str,
        security_token: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize SalesforcePasswordAuthMiddleware."""
        super().__init__(password=password + security_token, **kwargs)

    def _on_response(self, data: dict[str, Any]) -> None:
        """Extract and cache instance_url alongside the access token."""
        instance_url = self._extract_instance_url(data)
        super()._on_response(data)
        self._instance_url = instance_url


class AsyncSalesforceClientCredentialsAuthMiddleware(
    _SalesforceInstanceUrlAsyncMixin,
    AsyncOAuth2ClientCredentialsMiddleware,
):
    """Async OAuth2 auth middleware for the Salesforce Platform API.

    Async counterpart of ``SalesforceClientCredentialsAuthMiddleware``. Uses
    ``asyncio.Lock`` and ``HttpxAsyncTransport`` internally so the token
    endpoint is never called on a blocking thread.

    Extends ``AsyncOAuth2ClientCredentialsMiddleware`` to extract and cache
    the ``instance_url`` field from the Salesforce token response alongside
    the access token. Both are invalidated together on token expiry or a 401.
    """

    def _on_response(self, data: dict[str, Any]) -> None:
        """Extract and cache instance_url alongside the access token."""
        instance_url = self._extract_instance_url(data)
        super()._on_response(data)
        self._instance_url = instance_url


class AsyncSalesforcePasswordAuthMiddleware(
    _SalesforceInstanceUrlAsyncMixin,
    AsyncOAuth2PasswordMiddleware,
):
    """Async Salesforce OAuth2 Password middleware with cached ``instance_url``.

    Async counterpart of ``SalesforcePasswordAuthMiddleware``. Accepts the
    same ``security_token`` argument — when provided it is concatenated with
    *password* before the token request.

    Args:
        security_token: Optional Salesforce security token. When supplied,
            it is appended to ``password`` before the token request. Leave
            empty for orgs with IP allowlisting.

    """

    def __init__(
        self,
        *,
        password: str,
        security_token: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize AsyncSalesforcePasswordAuthMiddleware."""
        super().__init__(password=password + security_token, **kwargs)

    def _on_response(self, data: dict[str, Any]) -> None:
        """Extract and cache instance_url alongside the access token."""
        instance_url = self._extract_instance_url(data)
        super()._on_response(data)
        self._instance_url = instance_url


# ---------------------------------------------------------------------------
# JWT Bearer flow (SF-0006)
# ---------------------------------------------------------------------------

_JWT_MAX_EXP_SECONDS = 300  # Salesforce hard limit


def _build_jwt_assertion(
    client_id: str,
    username: str,
    audience: str,
    private_key: str | bytes,
    exp_seconds: int,
) -> str:
    """Return a signed RS256 JWT assertion for the Salesforce JWT Bearer flow."""
    if pyjwt is None:  # pragma: no cover
        raise ImportError(
            "The Salesforce JWT Bearer flow requires PyJWT and cryptography. "
            "Install them with: pip install 'PyJWT>=2.8' 'cryptography>=42' "
            "or use: pip install 'plynth[salesforce]'."
        )

    payload = {
        "iss": client_id,
        "sub": username,
        "aud": audience,
        "exp": int(time.time()) + exp_seconds,
    }
    token = cast(Any, pyjwt.encode(payload, private_key, algorithm="RS256"))
    if isinstance(token, str):
        return token
    if isinstance(token, bytes):
        return token.decode("utf-8")
    raise TypeError("PyJWT encode returned an unexpected token type")


def _audience_from_token_url(token_url: str) -> str:
    """Return the scheme + host of ``token_url`` for use as JWT ``aud``."""
    parts = urlsplit(token_url)
    return f"{parts.scheme}://{parts.netloc}"


class SalesforceJWTBearerAuthMiddleware(
    _SalesforceInstanceUrlSyncMixin,
    OAuth2JWTBearerMiddleware,
):
    """Salesforce OAuth2 JWT Bearer auth middleware (sync).

    Authenticates using a signed JWT assertion (RS256) instead of a shared
    secret. The JWT is built fresh on each token fetch and signed with the
    caller-supplied RSA private key. Salesforce verifies the signature
    against a certificate registered in the connected app or external client
    app.

    This is the recommended flow for server-to-server integrations. It is
    mandatory for orgs created Summer '23 or later where the
    Username-Password flow is blocked by default.

    All token lifecycle concerns (caching, lock, 401 invalidate-retry) are
    inherited from ``OAuth2AuthMiddlewareBase``. The Salesforce
    ``instance_url`` is extracted and cached alongside the access token via
    ``_SalesforceInstanceUrlSyncMixin``.

    Sandbox support: point ``token_url`` at
    ``https://test.salesforce.com/services/oauth2/token``; the JWT ``aud``
    is derived automatically from the host in ``token_url``.

    Args:
        client_id: Consumer key of the connected app or external client app.
        username: Salesforce username to authenticate as (must be
            pre-authorised in the connected app).
        private_key: RSA private key as a PEM-encoded string or bytes.
            Keep this value secret — load it from an environment variable
            or a secret manager, never hard-code it.
        token_url: Full URL of the Salesforce token endpoint, e.g.
            ``"https://login.salesforce.com/services/oauth2/token"``.
        jwt_exp_seconds: Lifetime of each JWT assertion in seconds.
            Default: 180. Must be between 1 and 300 (Salesforce hard limit).
        token_retry_policy: Optional retry policy for the token endpoint.
        ttl_leeway: Seconds subtracted from ``expires_in`` for early token
            refresh (default: 30).
        token_cache: Optional ``CacheBackend`` for token storage.

    Example::

        from plynth.http.transport import HttpxSyncTransport
        from plynth.connectors.salesforce.auth import SalesforceJWTBearerAuthMiddleware
        from plynth.connectors.salesforce.client import SalesforceAPIClient

        private_key = open("private_key.pem").read()

        auth = SalesforceJWTBearerAuthMiddleware(
            client_id="3MVG9...",
            username="integration@myorg.com",
            private_key=private_key,
            token_url="https://login.salesforce.com/services/oauth2/token",
        )
        transport = HttpxSyncTransport(middlewares=[auth])
        client = SalesforceAPIClient(auth=auth, transport=transport)

    """

    def __init__(
        self,
        *,
        client_id: str,
        username: str,
        private_key: str | bytes,
        token_url: str,
        jwt_exp_seconds: int = 180,
        **kwargs: Any,
    ) -> None:
        """Initialize SalesforceJWTBearerAuthMiddleware."""
        if not 1 <= jwt_exp_seconds <= _JWT_MAX_EXP_SECONDS:
            raise ValueError(
                f"jwt_exp_seconds must be between 1 and {_JWT_MAX_EXP_SECONDS}, "
                f"got {jwt_exp_seconds}."
            )
        self._client_id = client_id
        self._username = username
        self._private_key = private_key
        self._jwt_exp_seconds = jwt_exp_seconds
        self._audience = _audience_from_token_url(token_url)
        super().__init__(
            token_url=token_url,
            cache_key_material=f"{token_url}:{client_id}:{username}",
            assertion_factory=lambda: _build_jwt_assertion(
                client_id=self._client_id,
                username=self._username,
                audience=self._audience,
                private_key=self._private_key,
                exp_seconds=self._jwt_exp_seconds,
            ),
            **kwargs,
        )

    def _on_response(self, data: dict[str, Any]) -> None:
        """Extract and cache instance_url alongside the access token."""
        instance_url = self._extract_instance_url(data)
        super()._on_response(data)
        self._instance_url = instance_url


class AsyncSalesforceJWTBearerAuthMiddleware(
    _SalesforceInstanceUrlAsyncMixin,
    AsyncOAuth2JWTBearerMiddleware,
):
    """Salesforce OAuth2 JWT Bearer auth middleware (async).

    Async counterpart of ``SalesforceJWTBearerAuthMiddleware``. Uses
    ``asyncio.Lock`` and ``HttpxAsyncTransport`` internally so the token
    endpoint request never blocks the event loop.

    See ``SalesforceJWTBearerAuthMiddleware`` for full documentation on
    parameters and usage.

    Args:
        client_id: Consumer key of the connected app or external client app.
        username: Salesforce username to authenticate as.
        private_key: RSA private key as a PEM-encoded string or bytes.
        token_url: Full URL of the Salesforce token endpoint.
        jwt_exp_seconds: Lifetime of each JWT assertion in seconds
            (default: 180; max: 300).
        token_retry_policy: Optional retry policy for the token endpoint.
        ttl_leeway: Seconds subtracted from ``expires_in`` for early refresh.
        token_cache: Optional ``CacheBackend`` for token storage.

    """

    def __init__(
        self,
        *,
        client_id: str,
        username: str,
        private_key: str | bytes,
        token_url: str,
        jwt_exp_seconds: int = 180,
        **kwargs: Any,
    ) -> None:
        """Initialize AsyncSalesforceJWTBearerAuthMiddleware."""
        if not 1 <= jwt_exp_seconds <= _JWT_MAX_EXP_SECONDS:
            raise ValueError(
                f"jwt_exp_seconds must be between 1 and {_JWT_MAX_EXP_SECONDS}, "
                f"got {jwt_exp_seconds}."
            )
        self._client_id = client_id
        self._username = username
        self._private_key = private_key
        self._jwt_exp_seconds = jwt_exp_seconds
        self._audience = _audience_from_token_url(token_url)
        super().__init__(
            token_url=token_url,
            cache_key_material=f"{token_url}:{client_id}:{username}",
            assertion_factory=lambda: _build_jwt_assertion(
                client_id=self._client_id,
                username=self._username,
                audience=self._audience,
                private_key=self._private_key,
                exp_seconds=self._jwt_exp_seconds,
            ),
            **kwargs,
        )

    def _on_response(self, data: dict[str, Any]) -> None:
        """Extract and cache instance_url alongside the access token."""
        instance_url = self._extract_instance_url(data)
        super()._on_response(data)
        self._instance_url = instance_url


# Backward-compatible aliases (existing name = Client Credentials variant)
SalesforceOAuth2AuthMiddleware = SalesforceClientCredentialsAuthMiddleware
AsyncSalesforceOAuth2AuthMiddleware = AsyncSalesforceClientCredentialsAuthMiddleware

# Backward-compatible aliases for earlier verbose names.
SalesforceOAuth2ClientCredentialsAuthMiddleware = (
    SalesforceClientCredentialsAuthMiddleware
)
SalesforceOAuth2PasswordAuthMiddleware = SalesforcePasswordAuthMiddleware
AsyncSalesforceOAuth2ClientCredentialsAuthMiddleware = (
    AsyncSalesforceClientCredentialsAuthMiddleware
)
AsyncSalesforceOAuth2PasswordAuthMiddleware = AsyncSalesforcePasswordAuthMiddleware
