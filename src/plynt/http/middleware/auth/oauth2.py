"""OAuth2 auth middleware for Plynt.

Provides abstract bases and concrete implementations for OAuth2 flows.

**Sync classes:**

- ``OAuth2AuthMiddlewareBase`` — abstract; handles token lifecycle via
  ``CacheBackend``.
- ``OAuth2ClientCredentialsMiddleware`` — Client Credentials flow
  (machine-to-machine, ``grant_type=client_credentials``).
- ``OAuth2JWTBearerMiddleware`` — JWT Bearer flow
    (RFC 7523, ``grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer``).
- ``OAuth2PasswordMiddleware`` — Resource Owner Password Credentials flow
  (``grant_type=password``). Legacy; avoid for new integrations.
- ``OAuth2AuthMiddleware`` — backward-compatible alias for
  ``OAuth2ClientCredentialsMiddleware``.

**Async classes** (mirror the sync hierarchy):

- ``AsyncOAuth2AuthMiddlewareBase``
- ``AsyncOAuth2ClientCredentialsMiddleware``
- ``AsyncOAuth2JWTBearerMiddleware``
- ``AsyncOAuth2PasswordMiddleware``
- ``AsyncOAuth2AuthMiddleware`` — alias for
  ``AsyncOAuth2ClientCredentialsMiddleware``.

Token caching
~~~~~~~~~~~~~

Tokens are stored in a ``CacheBackend`` (``plynt.base.cache``). The
default backend is a per-instance ``LocMemCache`` — behavior equivalent to
the previous instance-variable approach.

Pass a *shared* backend to share tokens across instances or processes::

    from plynt.cache import LocMemCache, RedisCache

    # Shared in-process cache (e.g. two clients for the same API):
    shared_mem = LocMemCache()
    auth_a = OAuth2ClientCredentialsMiddleware(..., token_cache=shared_mem)
    auth_b = OAuth2ClientCredentialsMiddleware(..., token_cache=shared_mem)

    # Cross-process / cross-service cache:
    import redis
    cache = RedisCache(redis.Redis(...))
    auth = OAuth2ClientCredentialsMiddleware(..., token_cache=cache)

The cache stores ``(token, expires_at)`` tuples. ``expires_at`` is a
``time.monotonic()`` timestamp; the TTL passed to ``cache.set()``
matches this window so TTL-aware backends (Redis, LocMemCache) auto-expire
entries. ``DummyCache`` cannot store tokens and will raise a
``RuntimeError`` if used as ``token_cache``.

Install the ``[httpx]`` extra before using any OAuth2 middleware:
``pip install plynt[httpx]``.
"""

from __future__ import annotations

import abc
import asyncio
import hashlib
import json
import logging
import threading
import time
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any
from urllib.parse import urlencode

from plynt.base.cache import CacheBackend
from plynt.base.middleware import AsyncMiddleware, SyncMiddleware
from plynt.base.request import Request
from plynt.base.response import AsyncStreamingResponse, Response, StreamingResponse
from plynt.base.transport import AsyncTransport, SyncTransport
from plynt.http.policies import HttpRetryPolicy
from plynt.middleware.retry import AsyncRetryMiddleware, RetryMiddleware

__all__ = [
    "AsyncOAuth2AuthMiddleware",
    "AsyncOAuth2AuthMiddlewareBase",
    "AsyncOAuth2ClientCredentialsMiddleware",
    "AsyncOAuth2JWTBearerMiddleware",
    "AsyncOAuth2PasswordMiddleware",
    "OAuth2AuthMiddleware",
    "OAuth2AuthMiddlewareBase",
    "OAuth2ClientCredentialsMiddleware",
    "OAuth2JWTBearerMiddleware",
    "OAuth2PasswordMiddleware",
]

_CACHE_KEY_PREFIX = "plynt:oauth2:"
_JWT_BEARER_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"
JWTAssertionFactory = Callable[[], str]

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sync base
# ---------------------------------------------------------------------------


class OAuth2AuthMiddlewareBase(SyncMiddleware, abc.ABC):
    """Abstract base for sync OAuth2 auth middleware.

    Handles token fetch, caching, 401-retry, and invalidation. Subclasses
    must implement ``_cache_key_material()`` and ``_build_token_body()``
    to define the specific grant type.

    **Constructor ordering rule:** Subclasses must set their own attributes
    (e.g. ``_client_id``) **before** calling ``super().__init__()``, because
    the base computes the cache key in ``__init__`` by calling
    ``_cache_key_material()``.

    Token caching uses the ``CacheBackend`` protocol. Each entry is a
    ``(token, expires_at)`` tuple where ``expires_at`` is a
    ``time.monotonic()`` timestamp. The TTL passed to ``cache.set()``
    mirrors the tuple expiry to enable auto-expiry on TTL-aware backends.

    Args:
        token_url: Full URL of the token endpoint.
        token_retry_policy: Retry policy for token endpoint requests.
            Defaults to ``HttpRetryPolicy(max_attempts=2)`` when
            ``None``. Pass an explicit policy to control backoff and
            retryable status codes.
        ttl_leeway: Seconds subtracted from ``expires_in`` to avoid using
            a token that is about to expire. Default: ``30``.
        token_cache: ``CacheBackend`` for token storage. Defaults to a
            private ``LocMemCache`` (per-instance, in-process). Pass a
            shared backend to share tokens across instances or processes.
            ``DummyCache`` is not supported here.

    """

    def __init__(
        self,
        *,
        token_url: str,
        token_retry_policy: HttpRetryPolicy | None = None,
        ttl_leeway: int = 30,
        token_cache: CacheBackend | None = None,
    ) -> None:
        """Initialize OAuth2AuthMiddlewareBase."""
        self._token_url = token_url
        self._ttl_leeway = ttl_leeway
        self._lock = threading.Lock()
        if token_cache is None:
            # Deferred to keep plynt.cache off the main import path.
            from plynt.cache import LocMemCache

            token_cache = LocMemCache()
        self._cache: CacheBackend = token_cache
        self._cache_key: str = (
            _CACHE_KEY_PREFIX
            + hashlib.sha256(self._cache_key_material().encode()).hexdigest()
        )
        # Deferred to avoid circular dependency: auth → transport → auth
        from plynt.http.transport import HttpxSyncTransport
        from plynt.middleware.logging import LoggingMiddleware

        self._transport: SyncTransport = HttpxSyncTransport(
            middlewares=[
                LoggingMiddleware(logger=_logger, level=logging.DEBUG),
                RetryMiddleware(token_retry_policy or HttpRetryPolicy(max_attempts=2)),
            ],
        )

    @abc.abstractmethod
    def _cache_key_material(self) -> str:
        """Return a stable string used to build the cache key.

        Must uniquely identify the credential set and grant type. Called
        once during ``__init__``; subclass attributes set before
        ``super().__init__()`` are available.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    def _build_token_body(self) -> bytes:
        """Build the URL-encoded body for the token endpoint request."""
        ...  # pragma: no cover

    def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Response],
    ) -> Response:
        """Inject auth header, call next handler, and retry once on 401.

        Args:
            request: The outgoing request.
            next_handler: Next callable in the middleware chain.

        Returns:
            The response. On a 401, invalidates the cached token and
            retries exactly once; the second response is returned
            regardless. Discarded streams are closed before refreshing the token.

        """
        token_header = self._get_token_header()
        request.headers.update(token_header)
        used_token = token_header["Authorization"].removeprefix("Bearer ")
        response = next_handler(request)
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            _logger.debug("OAuth2 received 401 — invalidating token and retrying once")
            if isinstance(response, StreamingResponse):
                response.close()
            self._invalidate_if_matches(used_token)
            request.headers.update(self._get_token_header())
            response = next_handler(request)
        return response

    def _get_token_header(self) -> dict[str, str]:
        """Return a valid ``Authorization: Bearer …`` header (lazy fetch).

        Fetches a fresh token if none is cached or the cached entry has
        expired. Thread-safe: only one thread fetches at a time.
        """
        with self._lock:
            entry: tuple[str, float] | None = self._cache.get(self._cache_key)
            if entry is None or time.monotonic() >= entry[1]:
                _logger.debug(
                    "OAuth2 token cache miss — fetching from %s", self._token_url
                )
                self._fetch()
                entry = self._cache.get(self._cache_key)
            else:
                _logger.debug("OAuth2 token cache hit")
            if entry is None:  # pragma: no cover
                raise RuntimeError(
                    "Token fetch succeeded but the token was not stored in the "
                    "cache. DummyCache cannot be used as the OAuth2 token_cache "
                    "because it does not retain values. Use LocMemCache or "
                    "another backend."
                )
            return {"Authorization": f"Bearer {entry[0]}"}

    def _invalidate(self) -> None:
        """Discard the cached token so the next call retrieves a fresh one."""
        _logger.debug("OAuth2 token invalidated")
        with self._lock:
            self._cache.delete(self._cache_key)

    def _invalidate_if_matches(self, expected_token: str) -> None:
        """Invalidate the cache entry only when it still holds ``expected_token``."""
        with self._lock:
            entry: tuple[str, float] | None = self._cache.get(self._cache_key)
            if entry is not None and entry[0] == expected_token:
                _logger.debug("OAuth2 token invalidated for matching failed token")
                self._cache.delete(self._cache_key)

    def _fetch(self) -> None:
        """Send the token request and delegate storage to ``_on_response``.

        Must be called while the auth lock is held.
        """
        request = Request(
            method="POST",
            url=self._token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            content=self._build_token_body(),
        )
        response = self._transport.send(request)
        if response.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"Token endpoint returned {response.status_code}: {response.content!r}"
            )
        data = json.loads(response.content)
        self._on_response(data)

    def _on_response(self, data: dict[str, Any]) -> None:
        """Store the token and expiry from the parsed token response."""
        token: str = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        effective_ttl = max(float(expires_in - self._ttl_leeway), 1.0)
        expires_at = time.monotonic() + effective_ttl
        self._cache.set(self._cache_key, (token, expires_at), ttl=effective_ttl)
        _logger.debug("OAuth2 token stored, expires in %.0fs", effective_ttl)


# ---------------------------------------------------------------------------
# Concrete sync implementations
# ---------------------------------------------------------------------------


class OAuth2ClientCredentialsMiddleware(OAuth2AuthMiddlewareBase):
    """Sync OAuth2 Client Credentials flow (machine-to-machine).

    Fetches a bearer token using ``grant_type=client_credentials`` with
    client ID and secret. No user context is involved.

    On a 401 response, the cached token is invalidated and the request
    is retried once with a fresh token.

    Thread-safe: a ``threading.Lock`` ensures only one thread fetches
    at a time.

    Args:
        client_id: OAuth2 client identifier.
        client_secret: OAuth2 client secret.
        token_url: Full URL of the token endpoint.
        token_retry_policy: Retry policy for the token endpoint.
            Defaults to ``HttpRetryPolicy(max_attempts=2)`` when
            ``None``. Independent of the main transport's retry policy.
        ttl_leeway: Seconds subtracted from ``expires_in`` for early
            refresh (default: ``30``).
        token_cache: Optional ``CacheBackend`` for token storage.
            Defaults to a private in-process cache. Pass a shared backend
            (e.g. Redis) to share the token across instances or processes.

    Example::

        from http import HTTPStatus
        from plynt.http.middleware.auth import OAuth2ClientCredentialsMiddleware
        from plynt.http.policies import HttpRetryPolicy

        auth = OAuth2ClientCredentialsMiddleware(
            client_id="svc",
            client_secret="s3cr3t",
            token_url="https://auth.example.com/token",
            token_retry_policy=HttpRetryPolicy(
                max_attempts=3,
                retryable_status_codes=frozenset({
                    HTTPStatus.TOO_MANY_REQUESTS,
                    HTTPStatus.SERVICE_UNAVAILABLE,
                }),
            ),
        )

    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        token_url: str,
        token_retry_policy: HttpRetryPolicy | None = None,
        ttl_leeway: int = 30,
        token_cache: CacheBackend | None = None,
    ) -> None:
        """Initialize OAuth2ClientCredentialsMiddleware."""
        self._client_id = client_id
        self._client_secret = client_secret
        super().__init__(
            token_url=token_url,
            token_retry_policy=token_retry_policy,
            ttl_leeway=ttl_leeway,
            token_cache=token_cache,
        )

    def _cache_key_material(self) -> str:
        """Handle cache key material."""
        return f"cc:{self._token_url}:{self._client_id}"

    def _build_token_body(self) -> bytes:
        """Return the form-encoded body for a Client Credentials request."""
        return urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }
        ).encode()


#: Backward-compatible alias for ``OAuth2ClientCredentialsMiddleware``.
OAuth2AuthMiddleware = OAuth2ClientCredentialsMiddleware


class OAuth2PasswordMiddleware(OAuth2AuthMiddlewareBase):
    """Sync OAuth2 Resource Owner Password Credentials (ROPC) flow.

    Fetches a bearer token using ``grant_type=password`` with client
    credentials and a user's username and password. Suitable for trusted
    first-party applications only.

    .. warning::
        The ROPC flow is considered legacy and is prohibited in OAuth 2.1.
        Prefer ``OAuth2ClientCredentialsMiddleware`` for machine-to-machine
        use cases and Authorization Code for user-delegated access.

    On a 401 response, the cached token is invalidated and the request
    is retried once with a fresh token.

    Thread-safe: a ``threading.Lock`` ensures only one thread fetches
    at a time.

    Args:
        client_id: OAuth2 client identifier.
        client_secret: OAuth2 client secret.
        token_url: Full URL of the token endpoint.
        username: The resource owner's username.
        password: The resource owner's password.
        token_retry_policy: Retry policy for the token endpoint.
            Defaults to ``HttpRetryPolicy(max_attempts=2)`` when
            ``None``.
        ttl_leeway: Seconds subtracted from ``expires_in`` for early
            refresh (default: ``30``).
        token_cache: Optional ``CacheBackend`` for token storage.

    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        token_url: str,
        username: str,
        password: str,
        token_retry_policy: HttpRetryPolicy | None = None,
        ttl_leeway: int = 30,
        token_cache: CacheBackend | None = None,
    ) -> None:
        """Initialize OAuth2PasswordMiddleware."""
        self._client_id = client_id
        self._client_secret = client_secret
        self._username = username
        self._password = password
        super().__init__(
            token_url=token_url,
            token_retry_policy=token_retry_policy,
            ttl_leeway=ttl_leeway,
            token_cache=token_cache,
        )

    def _cache_key_material(self) -> str:
        """Handle cache key material."""
        return f"pw:{self._token_url}:{self._client_id}:{self._username}"

    def _build_token_body(self) -> bytes:
        """Return the form-encoded body for a Password Credentials request."""
        return urlencode(
            {
                "grant_type": "password",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "username": self._username,
                "password": self._password,
            }
        ).encode()


class OAuth2JWTBearerMiddleware(OAuth2AuthMiddlewareBase):
    """Sync OAuth2 JWT Bearer flow defined by RFC 7523.

    This middleware requests access tokens with a JWT assertion by sending
    ``grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer`` and an
    ``assertion`` parameter to the token endpoint.

    JWT creation is delegated to ``assertion_factory`` to keep the core
    package free from signing-library dependencies. This allows connector-
    specific implementations (for example Salesforce) to plug in their own
    JWT construction logic while reusing the generic OAuth2 token lifecycle.

    Args:
        token_url: Full URL of the token endpoint.
        assertion_factory: Callable that returns a signed JWT assertion.
            Called for each token fetch.
        cache_key_material: Stable identifier for cache key derivation.
            Must uniquely identify the credential set used by
            ``assertion_factory``.
        scope: Optional OAuth2 scope to include in the token request.
        token_retry_policy: Retry policy for the token endpoint.
        ttl_leeway: Seconds subtracted from ``expires_in`` for early refresh.
        token_cache: Optional ``CacheBackend`` for token storage.

    """

    def __init__(
        self,
        *,
        token_url: str,
        assertion_factory: JWTAssertionFactory,
        cache_key_material: str,
        scope: str | None = None,
        token_retry_policy: HttpRetryPolicy | None = None,
        ttl_leeway: int = 30,
        token_cache: CacheBackend | None = None,
    ) -> None:
        """Initialize OAuth2JWTBearerMiddleware."""
        self._assertion_factory = assertion_factory
        self._jwt_cache_key_material = cache_key_material
        self._scope = scope
        super().__init__(
            token_url=token_url,
            token_retry_policy=token_retry_policy,
            ttl_leeway=ttl_leeway,
            token_cache=token_cache,
        )

    def _cache_key_material(self) -> str:
        """Return material used to build the token cache key."""
        return f"jwt:{self._token_url}:{self._jwt_cache_key_material}"

    def _build_token_body(self) -> bytes:
        """Return the form-encoded body for an OAuth2 JWT Bearer request."""
        assertion = self._assertion_factory()
        if not isinstance(assertion, str):
            raise TypeError(
                "assertion_factory must return a JWT assertion string, "
                f"got {type(assertion).__name__}."
            )
        if not assertion:
            raise ValueError("assertion_factory returned an empty JWT assertion")

        payload: dict[str, str] = {
            "grant_type": _JWT_BEARER_GRANT_TYPE,
            "assertion": assertion,
        }
        if self._scope:
            payload["scope"] = self._scope
        return urlencode(payload).encode()


# ---------------------------------------------------------------------------
# Async base
# ---------------------------------------------------------------------------


class AsyncOAuth2AuthMiddlewareBase(AsyncMiddleware, abc.ABC):
    """Abstract base for async OAuth2 auth middleware.

    Async counterpart of ``OAuth2AuthMiddlewareBase``. Uses
    ``asyncio.Lock`` and ``HttpxAsyncTransport`` so token endpoint
    requests never block the event loop.

    See ``OAuth2AuthMiddlewareBase`` for full documentation on the
    constructor ordering rule, cache key contract, and override protocol
    for ``_on_response``.

    Args:
        token_url: Full URL of the token endpoint.
        token_retry_policy: Retry policy for token endpoint requests.
            Defaults to ``HttpRetryPolicy(max_attempts=2)`` when
            ``None``.
        ttl_leeway: Seconds subtracted from ``expires_in`` (default: ``30``).
        token_cache: Optional ``CacheBackend`` for token storage.

    """

    def __init__(
        self,
        *,
        token_url: str,
        token_retry_policy: HttpRetryPolicy | None = None,
        ttl_leeway: int = 30,
        token_cache: CacheBackend | None = None,
    ) -> None:
        """Initialize AsyncOAuth2AuthMiddlewareBase."""
        self._token_url = token_url
        self._ttl_leeway = ttl_leeway
        self._lock = asyncio.Lock()
        if token_cache is None:
            from plynt.cache import LocMemCache

            token_cache = LocMemCache()
        self._cache: CacheBackend = token_cache
        self._cache_key: str = (
            _CACHE_KEY_PREFIX
            + hashlib.sha256(self._cache_key_material().encode()).hexdigest()
        )
        # Deferred to avoid circular dependency: auth → transport → auth
        from plynt.http.transport import HttpxAsyncTransport
        from plynt.middleware.logging import AsyncLoggingMiddleware

        self._transport: AsyncTransport = HttpxAsyncTransport(
            middlewares=[
                AsyncLoggingMiddleware(logger=_logger, level=logging.DEBUG),
                AsyncRetryMiddleware(
                    token_retry_policy or HttpRetryPolicy(max_attempts=2)
                ),
            ],
        )

    @abc.abstractmethod
    def _cache_key_material(self) -> str:
        """Return a stable string used to build the cache key."""
        ...  # pragma: no cover

    @abc.abstractmethod
    def _build_token_body(self) -> bytes:
        """Build the URL-encoded body for the token endpoint request."""
        ...  # pragma: no cover

    async def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Inject auth header, await next handler, and retry once on 401."""
        token_header = await self._get_token_header()
        request.headers.update(token_header)
        used_token = token_header["Authorization"].removeprefix("Bearer ")
        response = await next_handler(request)
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            _logger.debug("OAuth2 received 401 — invalidating token and retrying once")
            if isinstance(response, AsyncStreamingResponse):
                await response.aclose()
            await self._invalidate_if_matches(used_token)
            request.headers.update(await self._get_token_header())
            response = await next_handler(request)
        return response

    async def _get_token_header(self) -> dict[str, str]:
        """Return a valid ``Authorization: Bearer …`` header (lazy fetch).

        Fetches a fresh token if none is cached or the cached entry has
        expired. Concurrency-safe: only one coroutine fetches at a time.
        """
        async with self._lock:
            entry: tuple[str, float] | None = self._cache.get(self._cache_key)
            if entry is None or time.monotonic() >= entry[1]:
                _logger.debug(
                    "OAuth2 token cache miss — fetching from %s", self._token_url
                )
                await self._fetch()
                entry = self._cache.get(self._cache_key)
            else:
                _logger.debug("OAuth2 token cache hit")
            if entry is None:  # pragma: no cover
                raise RuntimeError(
                    "Token fetch succeeded but the token was not stored in the "
                    "cache. DummyCache cannot be used as the OAuth2 token_cache "
                    "because it does not retain values. Use LocMemCache or "
                    "another backend."
                )
            return {"Authorization": f"Bearer {entry[0]}"}

    def _invalidate(self) -> None:
        """Discard the cached token so the next fetch retrieves a fresh one."""
        _logger.debug("OAuth2 token invalidated")
        self._cache.delete(self._cache_key)

    async def _invalidate_if_matches(self, expected_token: str) -> None:
        """Invalidate the cache entry only when it still holds ``expected_token``."""
        async with self._lock:
            entry: tuple[str, float] | None = self._cache.get(self._cache_key)
            if entry is not None and entry[0] == expected_token:
                _logger.debug("OAuth2 token invalidated for matching failed token")
                self._cache.delete(self._cache_key)

    async def _fetch(self) -> None:
        """Send the token request. Must be called while the auth lock is held."""
        request = Request(
            method="POST",
            url=self._token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            content=self._build_token_body(),
        )
        response = await self._transport.send(request)
        if response.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"Token endpoint returned {response.status_code}: {response.content!r}"
            )
        data = json.loads(response.content)
        self._on_response(data)

    def _on_response(self, data: dict[str, Any]) -> None:
        """Store the token and expiry from the parsed token response."""
        token: str = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        effective_ttl = max(float(expires_in - self._ttl_leeway), 1.0)
        expires_at = time.monotonic() + effective_ttl
        self._cache.set(self._cache_key, (token, expires_at), ttl=effective_ttl)
        _logger.debug("OAuth2 token stored, expires in %.0fs", effective_ttl)


# ---------------------------------------------------------------------------
# Concrete async implementations
# ---------------------------------------------------------------------------


class AsyncOAuth2ClientCredentialsMiddleware(AsyncOAuth2AuthMiddlewareBase):
    """Async OAuth2 Client Credentials flow.

    Async counterpart of ``OAuth2ClientCredentialsMiddleware``.

    Args:
        client_id: OAuth2 client identifier.
        client_secret: OAuth2 client secret.
        token_url: Full URL of the token endpoint.
        token_retry_policy: Retry policy for the token endpoint.
            Defaults to ``HttpRetryPolicy(max_attempts=2)`` when
            ``None``.
        ttl_leeway: Seconds subtracted from ``expires_in`` (default: ``30``).
        token_cache: Optional ``CacheBackend`` for token storage.

    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        token_url: str,
        token_retry_policy: HttpRetryPolicy | None = None,
        ttl_leeway: int = 30,
        token_cache: CacheBackend | None = None,
    ) -> None:
        """Initialize AsyncOAuth2ClientCredentialsMiddleware."""
        self._client_id = client_id
        self._client_secret = client_secret
        super().__init__(
            token_url=token_url,
            token_retry_policy=token_retry_policy,
            ttl_leeway=ttl_leeway,
            token_cache=token_cache,
        )

    def _cache_key_material(self) -> str:
        """Handle cache key material."""
        return f"cc:{self._token_url}:{self._client_id}"

    def _build_token_body(self) -> bytes:
        """Return the form-encoded body for a Client Credentials request."""
        return urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }
        ).encode()


#: Backward-compatible alias for
#: ``AsyncOAuth2ClientCredentialsMiddleware``.
AsyncOAuth2AuthMiddleware = AsyncOAuth2ClientCredentialsMiddleware


class AsyncOAuth2PasswordMiddleware(AsyncOAuth2AuthMiddlewareBase):
    """Async OAuth2 Resource Owner Password Credentials (ROPC) flow.

    Async counterpart of ``OAuth2PasswordMiddleware``. See that class for
    usage notes and security warnings.

    Args:
        client_id: OAuth2 client identifier.
        client_secret: OAuth2 client secret.
        token_url: Full URL of the token endpoint.
        username: The resource owner's username.
        password: The resource owner's password.
        token_retry_policy: Retry policy for the token endpoint.
            Defaults to ``HttpRetryPolicy(max_attempts=2)`` when
            ``None``.
        ttl_leeway: Seconds subtracted from ``expires_in`` (default: ``30``).
        token_cache: Optional ``CacheBackend`` for token storage.

    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        token_url: str,
        username: str,
        password: str,
        token_retry_policy: HttpRetryPolicy | None = None,
        ttl_leeway: int = 30,
        token_cache: CacheBackend | None = None,
    ) -> None:
        """Initialize AsyncOAuth2PasswordMiddleware."""
        self._client_id = client_id
        self._client_secret = client_secret
        self._username = username
        self._password = password
        super().__init__(
            token_url=token_url,
            token_retry_policy=token_retry_policy,
            ttl_leeway=ttl_leeway,
            token_cache=token_cache,
        )

    def _cache_key_material(self) -> str:
        """Handle cache key material."""
        return f"pw:{self._token_url}:{self._client_id}:{self._username}"

    def _build_token_body(self) -> bytes:
        """Return the form-encoded body for a Password Credentials request."""
        return urlencode(
            {
                "grant_type": "password",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "username": self._username,
                "password": self._password,
            }
        ).encode()


class AsyncOAuth2JWTBearerMiddleware(AsyncOAuth2AuthMiddlewareBase):
    """Async OAuth2 JWT Bearer flow defined by RFC 7523.

    Async counterpart of ``OAuth2JWTBearerMiddleware``.

    Args:
        token_url: Full URL of the token endpoint.
        assertion_factory: Callable that returns a signed JWT assertion.
            Called for each token fetch.
        cache_key_material: Stable identifier for cache key derivation.
            Must uniquely identify the credential set used by
            ``assertion_factory``.
        scope: Optional OAuth2 scope to include in the token request.
        token_retry_policy: Retry policy for the token endpoint.
        ttl_leeway: Seconds subtracted from ``expires_in`` for early refresh.
        token_cache: Optional ``CacheBackend`` for token storage.

    """

    def __init__(
        self,
        *,
        token_url: str,
        assertion_factory: JWTAssertionFactory,
        cache_key_material: str,
        scope: str | None = None,
        token_retry_policy: HttpRetryPolicy | None = None,
        ttl_leeway: int = 30,
        token_cache: CacheBackend | None = None,
    ) -> None:
        """Initialize AsyncOAuth2JWTBearerMiddleware."""
        self._assertion_factory = assertion_factory
        self._jwt_cache_key_material = cache_key_material
        self._scope = scope
        super().__init__(
            token_url=token_url,
            token_retry_policy=token_retry_policy,
            ttl_leeway=ttl_leeway,
            token_cache=token_cache,
        )

    def _cache_key_material(self) -> str:
        """Return material used to build the token cache key."""
        return f"jwt:{self._token_url}:{self._jwt_cache_key_material}"

    def _build_token_body(self) -> bytes:
        """Return the form-encoded body for an OAuth2 JWT Bearer request."""
        assertion = self._assertion_factory()
        if not isinstance(assertion, str):
            raise TypeError(
                "assertion_factory must return a JWT assertion string, "
                f"got {type(assertion).__name__}."
            )
        if not assertion:
            raise ValueError("assertion_factory returned an empty JWT assertion")

        payload: dict[str, str] = {
            "grant_type": _JWT_BEARER_GRANT_TYPE,
            "assertion": assertion,
        }
        if self._scope:
            payload["scope"] = self._scope
        return urlencode(payload).encode()
