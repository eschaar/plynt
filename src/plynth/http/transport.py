"""Concrete HTTP transport implementations backed by ``httpx``.

Provides both synchronous and asynchronous transports using ``httpx``.
``httpx`` must be installed via the ``[httpx]`` optional extra:

    pip install plynth[httpx]

Both transports extend ``BaseSyncTransport`` / ``BaseAsyncTransport``
(ADR-0013) — auth, retry, and caching are handled by the base class;
``_send_once()`` contains only the actual httpx I/O.

Each transport exposes a ``from_settings()`` class method that constructs
a fully configured instance from an ``HTTPSettings`` object (convention as
defined in ADR-0013; not abstract because each transport requires its own
settings type).

Example (sync)::

    from plynth.http.settings import HTTPSettings
    from plynth.http.transport import HttpxSyncTransport

    settings = HTTPSettings()
    transport = HttpxSyncTransport.from_settings(settings)
    resp = transport.send(Request(method="GET", url="https://api.example.com"))

Example (async)::

    transport = HttpxAsyncTransport.from_settings(settings)
    resp = await transport.send(Request(method="GET", url="https://api.example.com"))
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    import httpx
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "httpx is required for HttpxSyncTransport and HttpxAsyncTransport. "
        "Install it with: pip install plynth[httpx]"
    ) from exc

from plynth.base.middleware import AsyncMiddleware, SyncMiddleware
from plynth.base.request import Request
from plynth.base.response import AsyncStreamingResponse, Response, StreamingResponse
from plynth.base.transport import BaseAsyncTransport, BaseSyncTransport
from plynth.http.policies import HttpRetryPolicy
from plynth.http.response import HttpResponse
from plynth.middleware.retry import AsyncRetryMiddleware, RetryMiddleware

if TYPE_CHECKING:  # pragma: no cover
    from plynth.http.settings import HTTPSettings

__all__ = [
    "HttpxAsyncTransport",
    "HttpxSyncTransport",
    "scrub_headers",
    "scrub_url",
]

_logger = logging.getLogger(__name__)

# Headers that must never appear in log output (case-insensitive match).
_SCRUBBED_HEADERS: frozenset[str] = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "proxy-authorization",
    }
)

_SENSITIVE_QUERY_KEYS: frozenset[str] = frozenset(
    {
        "access_token",
        "apikey",
        "api_key",
        "authorization",
        "code",
        "password",
        "secret",
        "token",
    }
)


def scrub_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a copy of *headers* with sensitive values replaced.

    Any header whose lowercased name appears in the redaction list is
    replaced with ``"[REDACTED]"``. The original dict is never mutated.

    Args:
        headers: HTTP headers to sanitize.

    Returns:
        A new dict safe for inclusion in log records or error messages.

    Example::

        logged_headers = scrub_headers({"authorization": "Bearer token123"})
        # Result: {"authorization": "[REDACTED]"}

    """
    return {
        k: "[REDACTED]" if k.lower() in _SCRUBBED_HEADERS else v
        for k, v in headers.items()
    }


def scrub_url(url: str) -> str:
    """Return URL with sensitive query parameter values redacted.

    Query parameters whose names match the redaction list are replaced with
    ``"[REDACTED]"``. The rest of the URL is unchanged.

    Args:
        url: Full URL (with or without query string).

    Returns:
        The same URL with sensitive query parameter values replaced.

    Example::

        redacted = scrub_url("https://api.example.com?token=abc&user=john")
        # Result: "https://api.example.com?token=%5BREDACTED%5D&user=john"

    """
    split = urlsplit(url)
    if not split.query:
        return url

    redacted_query: list[tuple[str, str]] = []
    for key, value in parse_qsl(split.query, keep_blank_values=True):
        if key.lower() in _SENSITIVE_QUERY_KEYS:
            redacted_query.append((key, "[REDACTED]"))
        else:
            redacted_query.append((key, value))

    return urlunsplit(
        (
            split.scheme,
            split.netloc,
            split.path,
            urlencode(redacted_query),
            split.fragment,
        )
    )


def _build_httpx_client(settings: HTTPSettings) -> httpx.Client:
    """Construct an ``httpx.Client`` from ``HTTPSettings``."""
    return httpx.Client(
        timeout=httpx.Timeout(
            connect=settings.timeout_connect,
            read=settings.timeout_read,
            write=settings.timeout_write,
            pool=settings.timeout_pool,
        ),
        proxy=settings.proxy,
        verify=settings.verify,
        cert=settings.cert,
    )


def _build_httpx_async_client(settings: HTTPSettings) -> httpx.AsyncClient:
    """Construct an ``httpx.AsyncClient`` from ``HTTPSettings``."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=settings.timeout_connect,
            read=settings.timeout_read,
            write=settings.timeout_write,
            pool=settings.timeout_pool,
        ),
        proxy=settings.proxy,
        verify=settings.verify,
        cert=settings.cert,
    )


class HttpxSyncTransport(BaseSyncTransport):
    """Synchronous HTTP transport backed by ``httpx.Client``.

    Extends ``BaseSyncTransport`` — auth, retry, and middleware are handled
    by the base class. ``_send_once()`` contains only httpx I/O.

    Pass a pre-configured ``client`` for full control over connection
    pooling and advanced httpx settings.

    Args:
        client: Optional pre-configured ``httpx.Client``. When omitted,
            a default client is created.
        middlewares: Optional list of sync middleware. Use
            ``OAuth2AuthMiddleware``, ``BearerTokenAuthMiddleware``,
            ``RetryMiddleware``, or ``CacheMiddleware`` here.
        log_bodies: When ``True``, request and response bodies are logged
            at ``DEBUG`` level with sensitive headers scrubbed. **Never
            enable this in production.** Defaults to ``False``.

    Example::

        from plynth.http.middleware.auth import BearerTokenAuthMiddleware
        from plynth.middleware.retry import RetryMiddleware
        from plynth.http.policies import HttpRetryPolicy

        transport = HttpxSyncTransport(
            middlewares=[
                BearerTokenAuthMiddleware("my-token"),
                RetryMiddleware(HttpRetryPolicy(max_attempts=3)),
            ]
        )

    """

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        middlewares: list[SyncMiddleware] | None = None,
        log_bodies: bool = False,
    ) -> None:
        """Initialise a new ``HttpxSyncTransport``."""
        super().__init__(middlewares=middlewares)
        self._client = client or httpx.Client()
        self._log_bodies = log_bodies

    @classmethod
    def from_settings(cls, settings: HTTPSettings) -> HttpxSyncTransport:
        """Construct a fully configured transport from an ``HTTPSettings`` instance.

        Builds an ``httpx.Client`` and wires auth and retry middleware
        from the settings' ``auth`` property (ADR-0011).  Response and
        token caching are wired via the ``caches`` / ``default_cache`` /
        ``default_auth_cache`` properties (ADR-0010).

        """
        # Deferred to avoid a circular import: auth.py deferred-imports
        # HttpxSyncTransport inside oauth2 middleware __init__().
        from plynth.cache import cache_from_config
        from plynth.http.auth import auth_from_config
        from plynth.middleware.cache import CacheMiddleware

        middlewares: list[SyncMiddleware] = []
        caches = settings.caches

        # 1. Auth first so cache keys can include auth-derived request headers.
        # This prevents cache collisions across different credentials.
        auth_config = settings.auth
        if auth_config is not None:
            auth_token_cache = (
                cache_from_config(caches[settings.default_auth_cache])
                if caches
                and settings.default_auth_cache
                and settings.default_auth_cache in caches
                else None
            )
            middlewares.append(
                auth_from_config(auth_config, token_cache=auth_token_cache)
            )

        # 2. Response cache after auth, before retry.
        if caches and settings.default_cache and settings.default_cache in caches:
            middlewares.append(
                CacheMiddleware(cache_from_config(caches[settings.default_cache]))
            )

        # 3. Retry — innermost (wraps only the network call, ADR-0012).
        # Use the typed policy from settings.retry when provided; fall back
        # to a default HttpRetryPolicy built from the flat max_attempts field.
        retry_policy = settings.retry or HttpRetryPolicy(
            max_attempts=settings.max_attempts
        )
        middlewares.append(RetryMiddleware(retry_policy))

        return cls(
            client=_build_httpx_client(settings),
            middlewares=middlewares,
        )

    def _send_once(self, request: Request) -> Response:
        """Send a request using ``httpx`` (pure I/O, no auth/retry/cache).

        Raises:
            httpx.HTTPError: If a network or protocol error occurs.

        """
        if request.stream:
            return self._send_stream(request)

        safe_url = scrub_url(str(request.url))

        _logger.debug(
            "--> %s %s",
            request.method,
            safe_url,
            extra={
                "event.action": "http-request",
                "http.request.method": request.method,
                "url.full": safe_url,
            },
        )
        if self._log_bodies:
            _logger.debug(
                "--> %s %s body — headers: %s body: %s",
                request.method,
                safe_url,
                scrub_headers(request.headers),
                request.content,
                extra={"body_logging": True},
            )
        kwargs: dict[str, object] = {
            "method": request.method,
            "url": request.url,
            "headers": request.headers,
            "params": request.params,
            "content": request.content,
        }
        if request.timeout is not None:
            kwargs["timeout"] = request.timeout
        r = self._client.request(**kwargs)  # type: ignore[arg-type]
        _logger.debug(
            "<-- %d %s %s",
            r.status_code,
            request.method,
            safe_url,
            extra={
                "event.action": "http-request",
                "http.request.method": request.method,
                "http.response.status_code": r.status_code,
                "url.full": safe_url,
            },
        )
        if self._log_bodies:
            _logger.debug(
                "<-- %d %s %s body — headers: %s body: %s",
                r.status_code,
                request.method,
                safe_url,
                scrub_headers(dict(r.headers)),
                r.content,
                extra={"body_logging": True},
            )
        return HttpResponse(
            status_code=r.status_code,
            headers=dict(r.headers),
            content=r.content,
            method=request.method,
            url=str(request.url),
            _raw=r,
        )

    def _send_stream(self, request: Request) -> StreamingResponse:
        """Send a request in streaming mode and return a streaming response."""
        safe_url = scrub_url(str(request.url))

        _logger.debug(
            "--> %s %s",
            request.method,
            safe_url,
            extra={
                "event.action": "http-request",
                "http.request.method": request.method,
                "url.full": safe_url,
            },
        )

        request_kwargs: dict[str, object] = {
            "method": request.method,
            "url": request.url,
            "headers": request.headers,
            "params": request.params,
            "content": request.content,
        }
        raw_request = self._client.build_request(**request_kwargs)  # type: ignore[arg-type]

        send_kwargs: dict[str, object] = {"stream": True}
        if request.timeout is not None:
            send_kwargs["timeout"] = request.timeout

        raw_response = self._client.send(raw_request, **send_kwargs)  # type: ignore[arg-type]

        _logger.debug(
            "<-- %d %s %s (streaming, no body)",
            raw_response.status_code,
            request.method,
            safe_url,
            extra={
                "event.action": "http-response",
                "http.request.method": request.method,
                "http.response.status_code": raw_response.status_code,
                "http.response.streaming": True,
                "url.full": safe_url,
            },
        )

        return StreamingResponse(
            status_code=raw_response.status_code,
            headers=dict(raw_response.headers),
            _raw=raw_response,
        )

    def close(self) -> None:
        """Close the underlying httpx.Client and release all network resources."""
        self._client.close()

    def __enter__(self) -> HttpxSyncTransport:
        """Enter the runtime context for use in a with-statement."""
        return self

    def __exit__(self, *args: object) -> None:
        """Exit the runtime context and close the transport."""
        self.close()


class HttpxAsyncTransport(BaseAsyncTransport):
    """Asynchronous HTTP transport backed by ``httpx.AsyncClient``.

    Extends ``BaseAsyncTransport`` — auth, retry, and caching are handled
    by the base class. ``_send_once()`` contains only httpx I/O.

    Args:
        client: Optional pre-configured ``httpx.AsyncClient``. When
            omitted, a default client is created.
        middlewares: Optional list of async middleware. Use
            ``AsyncBearerTokenAuthMiddleware``, ``AsyncBasicAuthMiddleware``,
            ``AsyncRetryMiddleware``, or ``AsyncCacheMiddleware`` here.
        log_bodies: When ``True``, request and response bodies are logged
            at ``DEBUG`` level with sensitive headers scrubbed. **Never
            enable this in production.** Defaults to ``False``.

    """

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        middlewares: list[AsyncMiddleware] | None = None,
        log_bodies: bool = False,
    ) -> None:
        """Initialise a new ``HttpxAsyncTransport``."""
        super().__init__(middlewares=middlewares)
        self._client = client or httpx.AsyncClient()
        self._log_bodies = log_bodies

    @classmethod
    def from_settings(cls, settings: HTTPSettings) -> HttpxAsyncTransport:
        """Construct an async transport from an ``HTTPSettings`` instance.

        Auth is wired from the settings' ``auth`` property (ADR-0011).
        Response and token caching are wired via ``caches`` /
        ``default_cache`` / ``default_auth_cache`` (ADR-0010).

        """
        # Deferred to avoid a circular import: auth.py deferred-imports
        # HttpxSyncTransport inside oauth2 middleware __init__().
        from plynth.cache import cache_from_config
        from plynth.http.auth import async_auth_from_config
        from plynth.middleware.cache import AsyncCacheMiddleware

        middlewares: list[AsyncMiddleware] = []
        caches = settings.caches

        # 1. Auth first so cache keys can include auth-derived request headers.
        # This prevents cache collisions across different credentials.
        auth_config = settings.auth
        if auth_config is not None:
            auth_token_cache = (
                cache_from_config(caches[settings.default_auth_cache])
                if caches
                and settings.default_auth_cache
                and settings.default_auth_cache in caches
                else None
            )
            middlewares.append(
                async_auth_from_config(auth_config, token_cache=auth_token_cache)
            )

        # 2. Response cache after auth, before retry.
        if caches and settings.default_cache and settings.default_cache in caches:
            middlewares.append(
                AsyncCacheMiddleware(cache_from_config(caches[settings.default_cache]))
            )

        # 3. Retry — innermost (wraps only the network call, ADR-0012).
        # Use the typed policy from settings.retry when provided; fall back
        # to a default HttpRetryPolicy built from the flat max_attempts field.
        retry_policy = settings.retry or HttpRetryPolicy(
            max_attempts=settings.max_attempts
        )
        middlewares.append(AsyncRetryMiddleware(retry_policy))

        return cls(
            client=_build_httpx_async_client(settings),
            middlewares=middlewares,
        )

    async def _send_once(self, request: Request) -> Response:
        """Send a request asynchronously (pure I/O, no auth/retry/cache).

        Raises:
            httpx.HTTPError: If a network or protocol error occurs.

        """
        if request.stream:
            return await self._send_stream(request)

        safe_url = scrub_url(str(request.url))

        _logger.debug(
            "--> %s %s",
            request.method,
            safe_url,
            extra={
                "event.action": "http-request",
                "http.request.method": request.method,
                "url.full": safe_url,
            },
        )
        if self._log_bodies:
            _logger.debug(
                "--> %s %s body — headers: %s body: %s",
                request.method,
                safe_url,
                scrub_headers(request.headers),
                request.content,
                extra={"body_logging": True},
            )
        kwargs: dict[str, object] = {
            "method": request.method,
            "url": request.url,
            "headers": request.headers,
            "params": request.params,
            "content": request.content,
        }
        if request.timeout is not None:
            kwargs["timeout"] = request.timeout
        r = await self._client.request(**kwargs)  # type: ignore[arg-type]
        _logger.debug(
            "<-- %d %s %s",
            r.status_code,
            request.method,
            safe_url,
            extra={
                "event.action": "http-request",
                "http.request.method": request.method,
                "http.response.status_code": r.status_code,
                "url.full": safe_url,
            },
        )
        if self._log_bodies:
            _logger.debug(
                "<-- %d %s %s body — headers: %s body: %s",
                r.status_code,
                request.method,
                safe_url,
                scrub_headers(dict(r.headers)),
                r.content,
                extra={"body_logging": True},
            )
        return HttpResponse(
            status_code=r.status_code,
            headers=dict(r.headers),
            content=r.content,
            method=request.method,
            url=str(request.url),
            _raw=r,
        )

    async def _send_stream(self, request: Request) -> AsyncStreamingResponse:
        """Send a request in async streaming mode and return a streaming response."""
        safe_url = scrub_url(str(request.url))

        _logger.debug(
            "--> %s %s",
            request.method,
            safe_url,
            extra={
                "event.action": "http-request",
                "http.request.method": request.method,
                "url.full": safe_url,
            },
        )

        request_kwargs: dict[str, object] = {
            "method": request.method,
            "url": request.url,
            "headers": request.headers,
            "params": request.params,
            "content": request.content,
        }
        raw_request = self._client.build_request(**request_kwargs)  # type: ignore[arg-type]

        send_kwargs: dict[str, object] = {"stream": True}
        if request.timeout is not None:
            send_kwargs["timeout"] = request.timeout

        raw_response = await self._client.send(raw_request, **send_kwargs)  # type: ignore[arg-type]

        _logger.debug(
            "<-- %d %s %s (streaming, no body)",
            raw_response.status_code,
            request.method,
            safe_url,
            extra={
                "event.action": "http-response",
                "http.request.method": request.method,
                "http.response.status_code": raw_response.status_code,
                "http.response.streaming": True,
                "url.full": safe_url,
            },
        )

        return AsyncStreamingResponse(
            status_code=raw_response.status_code,
            headers=dict(raw_response.headers),
            _raw=raw_response,
        )

    async def aclose(self) -> None:
        """Close the underlying httpx.AsyncClient and release all network resources."""
        await self._client.aclose()

    async def __aenter__(self) -> HttpxAsyncTransport:
        """Enter the async runtime context for use in an async with-statement."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit the async runtime context and close the transport."""
        await self.aclose()
