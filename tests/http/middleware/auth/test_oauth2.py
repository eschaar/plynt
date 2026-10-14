"""Tests for all OAuth2 auth middleware: Client Credentials, Password, and base."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Callable
from typing import Any, cast

import pytest

from plynt.base.request import Request
from plynt.base.response import Response
from plynt.base.transport import AsyncTransport, SyncTransport
from plynt.cache import LocMemCache
from plynt.http.middleware.auth import (
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
from plynt.http.policies import HttpRetryPolicy
from plynt.http.settings import HTTPSettings
from plynt.http.transport import HttpxAsyncTransport, HttpxSyncTransport
from plynt.middleware.retry import AsyncRetryMiddleware, RetryMiddleware
from tests.http.conftest import (
    DUMMY_ACCESS_TOKEN,
    DUMMY_CLIENT_ID,
    DUMMY_CLIENT_SECRET,
    DUMMY_TOKEN_URL,
    _FakeAsyncTokenTransport,
    _FakeTokenTransport,
    _OAuthTestSettings,
)

# ---------------------------------------------------------------------------
# OAuth2AuthMiddleware (Client Credentials, sync)
# ---------------------------------------------------------------------------


class TestOAuth2AuthMiddleware:
    """Test suite for OAuth2AuthMiddleware."""

    def _make_auth(
        self,
        oauth_settings: _OAuthTestSettings,
        token_transport: _FakeTokenTransport,
        **kwargs: Any,
    ) -> OAuth2AuthMiddleware:
        """Construct an OAuth2AuthMiddleware with a stubbed internal transport."""
        auth = OAuth2AuthMiddleware(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
            **kwargs,
        )
        auth._transport = token_transport  # stub after construction
        return auth

    def test_get_token_header_returns_bearer_header(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """Validate get token header returns bearer header."""
        auth = self._make_auth(oauth_settings, token_transport)
        headers = auth._get_token_header()
        assert headers == {"Authorization": f"Bearer {DUMMY_ACCESS_TOKEN}"}
        assert token_transport.calls == 1

    def test_token_is_cached_between_calls(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """Validate token is cached between calls."""
        auth = self._make_auth(oauth_settings, token_transport)
        auth._get_token_header()
        auth._get_token_header()
        assert token_transport.calls == 1

    def test_invalidate_forces_refetch(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """Validate invalidate forces refetch."""
        auth = self._make_auth(oauth_settings, token_transport)
        auth._get_token_header()
        auth._invalidate()
        auth._get_token_header()
        assert token_transport.calls == 2

    def test_invalidate_if_matches_skips_newer_cached_token(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """Validate conditional invalidation does not delete a fresher token."""
        auth = self._make_auth(oauth_settings, token_transport)
        auth._cache.set(auth._cache_key, ("fresh-token", time.monotonic() + 60), ttl=60)

        auth._invalidate_if_matches("stale-token")

        entry = auth._cache.get(auth._cache_key)
        assert entry is not None
        assert entry[0] == "fresh-token"

    def test_raises_on_non_200_token_response(
        self, oauth_settings: _OAuthTestSettings
    ) -> None:
        """Validate raises on non 200 token response."""
        auth = OAuth2AuthMiddleware(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
        )
        auth._transport = _FakeTokenTransport(status=401)
        with pytest.raises(RuntimeError, match="401"):
            auth._get_token_header()

    def test_handle_injects_auth_and_calls_next(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """Validate handle injects auth and calls next."""
        auth = self._make_auth(oauth_settings, token_transport)
        req = Request(method="GET", url="https://example.com")
        received_headers: list[dict[str, str]] = []

        def _next(r: Request) -> Response:
            """Handle next."""
            received_headers.append(dict(r.headers))
            return Response(status_code=200, content=b"")

        resp = auth.handle(req, _next)
        assert resp.status_code == 200
        assert received_headers[0].get("Authorization") == (
            f"Bearer {DUMMY_ACCESS_TOKEN}"
        )

    def test_handle_retries_on_401(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """On a 401, the token is invalidated and the request retried once."""
        auth = self._make_auth(oauth_settings, token_transport)
        req = Request(method="GET", url="https://example.com")
        call_count: list[int] = [0]

        def _next(r: Request) -> Response:
            """Handle next."""
            call_count[0] += 1
            status = 401 if call_count[0] == 1 else 200
            return Response(status_code=status, content=b"")

        resp = auth.handle(req, _next)
        assert resp.status_code == 200
        assert call_count[0] == 2

    def test_handle_does_not_retry_twice_on_401(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """A persistent 401 is returned as-is after one retry."""
        auth = self._make_auth(oauth_settings, token_transport)
        req = Request(method="GET", url="https://example.com")

        resp = auth.handle(req, lambda r: Response(status_code=401, content=b""))
        assert resp.status_code == 401

    def test_token_endpoint_receives_correct_body(self) -> None:
        """Verify that client_id and client_secret are sent in the POST body."""
        seen_body: list[bytes | None] = []

        class _CapturingTransport(SyncTransport):
            """Represent CapturingTransport."""

            def send(self, request: Request) -> Response:
                """Return send."""
                seen_body.append(request.content)
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": "t", "expires_in": 60}
                    ).encode(),
                )

        auth = OAuth2AuthMiddleware(
            client_id="my-client",
            client_secret="my-secret",
            token_url=DUMMY_TOKEN_URL,
        )
        auth._transport = _CapturingTransport()
        auth._get_token_header()

        assert seen_body
        assert seen_body[0] is not None
        body_str = seen_body[0].decode()
        assert "client_id=my-client" in body_str
        assert "client_secret=my-secret" in body_str
        assert "grant_type=client_credentials" in body_str

    def test_token_refreshed_after_expiry(self) -> None:
        """A token past its TTL triggers a new fetch."""

        class _ExpiringTransport(SyncTransport):
            """Represent ExpiringTransport."""

            calls: int = 0

            def send(self, request: Request) -> Response:
                """Return send."""
                self.calls += 1
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": f"token-{self.calls}", "expires_in": 1}
                    ).encode(),
                )

        stub = _ExpiringTransport()
        auth = OAuth2AuthMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
            ttl_leeway=0,
        )
        auth._transport = stub
        auth._get_token_header()
        # Simulate expiry by backdating the cache entry.
        auth._cache.set(auth._cache_key, ("token-1", time.monotonic() - 1.0))
        auth._get_token_header()
        assert stub.calls == 2

    def test_thread_safe_single_fetch(self) -> None:
        """Only one thread fetches the token when multiple threads call
        _get_token_header() concurrently."""
        fetch_count: list[int] = [0]
        lock = threading.Lock()

        class _SlowTransport(SyncTransport):
            """Represent SlowTransport."""

            def send(self, request: Request) -> Response:
                """Return send."""
                with lock:
                    fetch_count[0] += 1
                time.sleep(0.01)
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": "shared-token", "expires_in": 3600}
                    ).encode(),
                )

        auth = OAuth2AuthMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
        )
        auth._transport = _SlowTransport()

        results: list[dict[str, str]] = []

        def call() -> None:
            """Return call."""
            results.append(auth._get_token_header())

        threads = [threading.Thread(target=call) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert fetch_count[0] == 1
        assert all(h == {"Authorization": "Bearer shared-token"} for h in results)

    def test_internal_transport_is_httpx_sync(self) -> None:
        """OAuth2AuthMiddleware always creates an internal HttpxSyncTransport."""
        auth = OAuth2AuthMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
        )
        assert isinstance(auth._transport, HttpxSyncTransport)

    def test_internal_transport_uses_token_retry_policy(self) -> None:
        """token_retry_policy is wired into the internal transport's RetryMiddleware."""
        policy = HttpRetryPolicy(max_attempts=5)
        auth = OAuth2AuthMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
            token_retry_policy=policy,
        )
        assert isinstance(auth._transport, HttpxSyncTransport)
        retry_mw = auth._transport._middlewares[1]
        assert isinstance(retry_mw, RetryMiddleware)
        assert isinstance(retry_mw._policy, HttpRetryPolicy)
        assert retry_mw._policy is policy

    def test_internal_transport_defaults_to_max_attempts_2(self) -> None:
        """Without token_retry_policy, the internal transport uses max_attempts=2."""
        auth = OAuth2AuthMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
        )
        retry_mw = auth._transport._middlewares[1]  # type: ignore[attr-defined]
        assert isinstance(retry_mw, RetryMiddleware)
        assert retry_mw._policy.max_attempts == 2

    def test_from_settings_wires_token_retry_policy(
        self, oauth_settings: _OAuthTestSettings
    ) -> None:
        """from_settings() forwards token_retry_policy from the auth config.

        The policy is wired identity-equal into the internal transport middleware.
        """
        from plynt.http.auth import OAuth2ClientCredentialsConfig

        policy = HttpRetryPolicy(max_attempts=4)

        class _Settings(HTTPSettings):
            """Represent Settings."""

            @property
            def auth(self) -> OAuth2ClientCredentialsConfig:
                """Return auth."""
                return OAuth2ClientCredentialsConfig(
                    client_id=oauth_settings.client_id,
                    client_secret=oauth_settings.client_secret,
                    token_url=oauth_settings.token_url,
                    token_retry_policy=policy,
                )

        transport = HttpxSyncTransport.from_settings(_Settings())
        auth = transport._middlewares[0]
        assert isinstance(auth, OAuth2AuthMiddleware)
        retry_mw = auth._transport._middlewares[1]  # type: ignore[attr-defined]
        assert isinstance(retry_mw, RetryMiddleware)
        assert retry_mw._policy is policy
        transport.close()

    def test_on_response_hook_called_after_fetch(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """_on_response is called with the parsed token response dict."""
        received: list[dict[str, object]] = []

        class _HookCapture(OAuth2AuthMiddleware):
            """Represent HookCapture."""

            def _on_response(self, data: dict[str, object]) -> None:
                """Handle on response."""
                super()._on_response(data)
                received.append(data)

        auth = _HookCapture(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
        )
        auth._transport = token_transport
        auth._get_token_header()

        assert len(received) == 1
        assert received[0]["access_token"] == DUMMY_ACCESS_TOKEN

    def test_on_response_hook_not_called_on_cached_token(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """_on_response is only called when the token endpoint is hit."""
        call_count: list[int] = [0]

        class _CountingHook(OAuth2AuthMiddleware):
            """Represent CountingHook."""

            def _on_response(self, data: dict[str, object]) -> None:
                """Handle on response."""
                super()._on_response(data)
                call_count[0] += 1

        auth = _CountingHook(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
        )
        auth._transport = token_transport
        auth._get_token_header()
        auth._get_token_header()  # cache hit - hook must not be called again

        assert call_count[0] == 1

    def test_on_response_stores_token_and_expiry(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """Base _on_response stores the token and expiry in the cache backend."""
        auth = self._make_auth(oauth_settings, token_transport)
        auth._on_response({"access_token": "my-token", "expires_in": 100})
        entry = auth._cache.get(auth._cache_key)
        assert entry is not None
        token, expires_at = entry
        assert token == "my-token"
        assert expires_at > time.monotonic()


# ---------------------------------------------------------------------------
# AsyncOAuth2AuthMiddleware (Client Credentials, async)
# ---------------------------------------------------------------------------


class TestAsyncOAuth2AuthMiddleware:
    """Test suite for AsyncOAuth2AuthMiddleware."""

    def _make_auth(
        self,
        oauth_settings: _OAuthTestSettings,
        token_transport: _FakeAsyncTokenTransport,
        **kwargs: Any,
    ) -> AsyncOAuth2AuthMiddleware:
        """Construct an AsyncOAuth2AuthMiddleware with a stubbed internal transport."""
        auth = AsyncOAuth2AuthMiddleware(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
            **kwargs,
        )
        auth._transport = token_transport
        return auth

    async def test_get_token_header_returns_bearer_header(
        self,
        oauth_settings: _OAuthTestSettings,
        async_token_transport: _FakeAsyncTokenTransport,
    ) -> None:
        """Validate get token header returns bearer header."""
        auth = self._make_auth(oauth_settings, async_token_transport)
        headers = await auth._get_token_header()
        assert headers == {"Authorization": f"Bearer {DUMMY_ACCESS_TOKEN}"}
        assert async_token_transport.calls == 1

    async def test_token_is_cached_between_calls(
        self,
        oauth_settings: _OAuthTestSettings,
        async_token_transport: _FakeAsyncTokenTransport,
    ) -> None:
        """Validate token is cached between calls."""
        auth = self._make_auth(oauth_settings, async_token_transport)
        await auth._get_token_header()
        await auth._get_token_header()
        assert async_token_transport.calls == 1

    async def test_invalidate_forces_refetch(
        self,
        oauth_settings: _OAuthTestSettings,
        async_token_transport: _FakeAsyncTokenTransport,
    ) -> None:
        """Validate invalidate forces refetch."""
        auth = self._make_auth(oauth_settings, async_token_transport)
        await auth._get_token_header()
        auth._invalidate()
        await auth._get_token_header()
        assert async_token_transport.calls == 2

    async def test_invalidate_if_matches_skips_newer_cached_token(
        self,
        oauth_settings: _OAuthTestSettings,
        async_token_transport: _FakeAsyncTokenTransport,
    ) -> None:
        """Validate conditional invalidation does not delete a fresher token."""
        auth = self._make_auth(oauth_settings, async_token_transport)
        auth._cache.set(auth._cache_key, ("fresh-token", time.monotonic() + 60), ttl=60)

        await auth._invalidate_if_matches("stale-token")

        entry = auth._cache.get(auth._cache_key)
        assert entry is not None
        assert entry[0] == "fresh-token"

    async def test_raises_on_non_200_token_response(
        self,
        oauth_settings: _OAuthTestSettings,
    ) -> None:
        """Validate raises on non 200 token response."""
        auth = AsyncOAuth2AuthMiddleware(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
        )
        auth._transport = _FakeAsyncTokenTransport(status=401)
        with pytest.raises(RuntimeError, match="401"):
            await auth._get_token_header()

    async def test_handle_injects_auth_and_calls_next(
        self,
        oauth_settings: _OAuthTestSettings,
        async_token_transport: _FakeAsyncTokenTransport,
    ) -> None:
        """Validate handle injects auth and calls next."""
        auth = self._make_auth(oauth_settings, async_token_transport)
        req = Request(method="GET", url="https://example.com")
        received_headers: list[dict[str, str]] = []

        async def _next(r: Request) -> Response:
            """Handle next."""
            received_headers.append(dict(r.headers))
            return Response(status_code=200, content=b"")

        resp = await auth.handle(req, _next)
        assert resp.status_code == 200
        assert received_headers[0].get("Authorization") == (
            f"Bearer {DUMMY_ACCESS_TOKEN}"
        )

    async def test_handle_retries_on_401(
        self,
        oauth_settings: _OAuthTestSettings,
        async_token_transport: _FakeAsyncTokenTransport,
    ) -> None:
        """On a 401, the token is invalidated and the request retried once."""
        auth = self._make_auth(oauth_settings, async_token_transport)
        req = Request(method="GET", url="https://example.com")
        call_count: list[int] = [0]

        async def _next(r: Request) -> Response:
            """Handle next."""
            call_count[0] += 1
            status = 401 if call_count[0] == 1 else 200
            return Response(status_code=status, content=b"")

        resp = await auth.handle(req, _next)
        assert resp.status_code == 200
        assert call_count[0] == 2

    async def test_handle_does_not_retry_twice_on_401(
        self,
        oauth_settings: _OAuthTestSettings,
        async_token_transport: _FakeAsyncTokenTransport,
    ) -> None:
        """A persistent 401 is returned as-is after one retry."""
        auth = self._make_auth(oauth_settings, async_token_transport)
        req = Request(method="GET", url="https://example.com")

        async def _always_401(r: Request) -> Response:
            """Handle always 401."""
            return Response(status_code=401, content=b"")

        resp = await auth.handle(req, _always_401)
        assert resp.status_code == 401

    async def test_token_endpoint_receives_correct_body(
        self,
        oauth_settings: _OAuthTestSettings,
    ) -> None:
        """Verify that client_id and client_secret are sent in the POST body."""
        seen_body: list[bytes | None] = []

        class _CapturingAsyncTransport(AsyncTransport):
            """Represent CapturingAsyncTransport."""

            async def send(self, request: Request) -> Response:
                """Return send."""
                seen_body.append(request.content)
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": "t", "expires_in": 60}
                    ).encode(),
                )

        auth = AsyncOAuth2AuthMiddleware(
            client_id="my-client",
            client_secret="my-secret",
            token_url=DUMMY_TOKEN_URL,
        )
        auth._transport = _CapturingAsyncTransport()
        await auth._get_token_header()

        assert seen_body
        assert seen_body[0] is not None
        body_str = seen_body[0].decode()
        assert "client_id=my-client" in body_str
        assert "client_secret=my-secret" in body_str
        assert "grant_type=client_credentials" in body_str

    async def test_token_refreshed_after_expiry(
        self,
        oauth_settings: _OAuthTestSettings,
    ) -> None:
        """A token past its TTL triggers a new fetch."""

        class _ExpiringAsyncTransport(AsyncTransport):
            """Represent ExpiringAsyncTransport."""

            calls: int = 0

            async def send(self, request: Request) -> Response:
                """Return send."""
                self.calls += 1
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": f"token-{self.calls}", "expires_in": 1}
                    ).encode(),
                )

        stub = _ExpiringAsyncTransport()
        auth = AsyncOAuth2AuthMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
            ttl_leeway=0,
        )
        auth._transport = stub
        await auth._get_token_header()
        # Simulate expiry by backdating the cache entry.
        auth._cache.set(auth._cache_key, ("token-1", time.monotonic() - 1.0))
        await auth._get_token_header()
        assert stub.calls == 2

    async def test_concurrent_calls_fetch_once(
        self,
        oauth_settings: _OAuthTestSettings,
    ) -> None:
        """Concurrent coroutines share the token; the endpoint is called once."""
        fetch_count: list[int] = [0]

        class _SlowAsyncTransport(AsyncTransport):
            """Represent SlowAsyncTransport."""

            async def send(self, request: Request) -> Response:
                """Return send."""
                fetch_count[0] += 1
                await asyncio.sleep(0)
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": "shared-token", "expires_in": 3600}
                    ).encode(),
                )

        auth = AsyncOAuth2AuthMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
        )
        auth._transport = _SlowAsyncTransport()

        results = await asyncio.gather(*[auth._get_token_header() for _ in range(5)])
        assert fetch_count[0] == 1
        assert all(h == {"Authorization": "Bearer shared-token"} for h in results)

    async def test_internal_transport_is_httpx_async(
        self,
        oauth_settings: _OAuthTestSettings,
    ) -> None:
        """AsyncOAuth2AuthMiddleware always creates an internal HttpxAsyncTransport."""
        auth = AsyncOAuth2AuthMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
        )
        assert isinstance(auth._transport, HttpxAsyncTransport)

    async def test_internal_transport_uses_token_retry_policy(
        self,
        oauth_settings: _OAuthTestSettings,
    ) -> None:
        """token_retry_policy is wired into the async internal transport."""
        policy = HttpRetryPolicy(max_attempts=5)
        auth = AsyncOAuth2AuthMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
            token_retry_policy=policy,
        )
        assert isinstance(auth._transport, HttpxAsyncTransport)
        retry_mw = auth._transport._middlewares[1]
        assert isinstance(retry_mw, AsyncRetryMiddleware)
        assert isinstance(retry_mw._policy, HttpRetryPolicy)
        assert retry_mw._policy is policy

    async def test_internal_transport_defaults_to_max_attempts_2(
        self,
        oauth_settings: _OAuthTestSettings,
    ) -> None:
        """Without token_retry_policy, async internal transport uses max_attempts=2."""
        auth = AsyncOAuth2AuthMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
        )
        retry_mw = auth._transport._middlewares[1]  # type: ignore[attr-defined]
        assert isinstance(retry_mw, AsyncRetryMiddleware)
        assert retry_mw._policy.max_attempts == 2

    async def test_on_response_hook_called_after_fetch(
        self,
        oauth_settings: _OAuthTestSettings,
        async_token_transport: _FakeAsyncTokenTransport,
    ) -> None:
        """_on_response is called with the parsed token response dict."""
        received: list[dict[str, Any]] = []

        class _HookCapture(AsyncOAuth2AuthMiddleware):
            """Represent HookCapture."""

            def _on_response(self, data: dict[str, Any]) -> None:
                """Handle on response."""
                super()._on_response(data)
                received.append(data)

        auth = _HookCapture(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
        )
        auth._transport = async_token_transport
        await auth._get_token_header()

        assert len(received) == 1
        assert received[0]["access_token"] == DUMMY_ACCESS_TOKEN

    async def test_on_response_hook_not_called_on_cached_token(
        self,
        oauth_settings: _OAuthTestSettings,
        async_token_transport: _FakeAsyncTokenTransport,
    ) -> None:
        """_on_response is only called when the token endpoint is hit."""
        call_count: list[int] = [0]

        class _CountingHook(AsyncOAuth2AuthMiddleware):
            """Represent CountingHook."""

            def _on_response(self, data: dict[str, Any]) -> None:
                """Handle on response."""
                super()._on_response(data)
                call_count[0] += 1

        auth = _CountingHook(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
        )
        auth._transport = async_token_transport
        await auth._get_token_header()
        await auth._get_token_header()  # cache hit — hook must not be called again

        assert call_count[0] == 1

    async def test_on_response_stores_token_and_expiry(
        self,
        oauth_settings: _OAuthTestSettings,
        async_token_transport: _FakeAsyncTokenTransport,
    ) -> None:
        """Base _on_response stores the token and expiry in the cache backend."""
        auth = self._make_auth(oauth_settings, async_token_transport)
        auth._on_response({"access_token": "my-token", "expires_in": 100})
        entry = auth._cache.get(auth._cache_key)
        assert entry is not None
        token, expires_at = entry
        assert token == "my-token"
        assert expires_at > time.monotonic()


# ---------------------------------------------------------------------------
# OAuth2AuthMiddlewareBase — abstract contract
# ---------------------------------------------------------------------------


class TestOAuth2AuthMiddlewareBase:
    """Test suite for OAuth2AuthMiddlewareBase."""

    def test_cannot_instantiate_directly(self) -> None:
        """OAuth2AuthMiddlewareBase is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            OAuth2AuthMiddlewareBase(  # type: ignore[abstract]
                token_url=DUMMY_TOKEN_URL,
            )

    def test_oauth2auth_middleware_is_alias_for_client_credentials(self) -> None:
        """OAuth2AuthMiddleware is a backward-compatible alias."""
        assert OAuth2AuthMiddleware is OAuth2ClientCredentialsMiddleware

    def test_client_credentials_is_subclass_of_base(self) -> None:
        """Validate client credentials is subclass of base."""
        assert issubclass(OAuth2ClientCredentialsMiddleware, OAuth2AuthMiddlewareBase)

    def test_password_is_subclass_of_base(self) -> None:
        """Validate password is subclass of base."""
        assert issubclass(OAuth2PasswordMiddleware, OAuth2AuthMiddlewareBase)


# ---------------------------------------------------------------------------
# OAuth2PasswordMiddleware (sync)
# ---------------------------------------------------------------------------


class TestOAuth2PasswordMiddleware:
    """Test suite for OAuth2PasswordMiddleware."""

    _USERNAME = "alice"
    _PASSWORD = "s3cr3t"

    def _make_auth(
        self,
        oauth_settings: _OAuthTestSettings,
        token_transport: _FakeTokenTransport,
        **kwargs: Any,
    ) -> OAuth2PasswordMiddleware:
        """Handle make auth."""
        auth = OAuth2PasswordMiddleware(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
            username=self._USERNAME,
            password=self._PASSWORD,
            **kwargs,
        )
        auth._transport = token_transport
        return auth

    def test_get_token_header_returns_bearer_header(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """Validate get token header returns bearer header."""
        auth = self._make_auth(oauth_settings, token_transport)
        headers = auth._get_token_header()
        assert headers == {"Authorization": f"Bearer {DUMMY_ACCESS_TOKEN}"}
        assert token_transport.calls == 1

    def test_token_is_cached_between_calls(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """Validate token is cached between calls."""
        auth = self._make_auth(oauth_settings, token_transport)
        auth._get_token_header()
        auth._get_token_header()
        assert token_transport.calls == 1

    def test_invalidate_forces_refetch(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """Validate invalidate forces refetch."""
        auth = self._make_auth(oauth_settings, token_transport)
        auth._get_token_header()
        auth._invalidate()
        auth._get_token_header()
        assert token_transport.calls == 2

    def test_token_body_contains_grant_type_password(self) -> None:
        """Token request body uses grant_type=password."""
        seen_body: list[bytes] = []

        class _CapturingTransport(SyncTransport):
            """Represent CapturingTransport."""

            def send(self, request: Request) -> Response:
                """Return send."""
                seen_body.append(request.content or b"")
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": "t", "expires_in": 60}
                    ).encode(),
                )

        auth = OAuth2PasswordMiddleware(
            client_id="my-client",
            client_secret="my-secret",
            token_url=DUMMY_TOKEN_URL,
            username=self._USERNAME,
            password=self._PASSWORD,
        )
        auth._transport = _CapturingTransport()
        auth._get_token_header()

        assert seen_body
        body_str = seen_body[0].decode()
        assert "grant_type=password" in body_str
        assert "client_id=my-client" in body_str
        assert "client_secret=my-secret" in body_str
        assert f"username={self._USERNAME}" in body_str
        assert f"password={self._PASSWORD}" in body_str

    def test_cache_key_differs_from_client_credentials(
        self, oauth_settings: _OAuthTestSettings
    ) -> None:
        """Password middleware has a different cache key than client credentials."""
        pw = OAuth2PasswordMiddleware(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
            username=self._USERNAME,
            password=self._PASSWORD,
        )
        cc = OAuth2ClientCredentialsMiddleware(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
        )
        assert pw._cache_key != cc._cache_key

    def test_different_usernames_produce_different_cache_keys(
        self, oauth_settings: _OAuthTestSettings
    ) -> None:
        """Two Password middlewares with different users get separate cache keys."""
        auth_a = OAuth2PasswordMiddleware(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
            username="user-a",
            password="pass-a",
        )
        auth_b = OAuth2PasswordMiddleware(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
            username="user-b",
            password="pass-b",
        )
        assert auth_a._cache_key != auth_b._cache_key

    def test_handle_retries_on_401(
        self, oauth_settings: _OAuthTestSettings, token_transport: _FakeTokenTransport
    ) -> None:
        """Validate handle retries on 401."""
        auth = self._make_auth(oauth_settings, token_transport)
        req = Request(method="GET", url="https://example.com")
        call_count: list[int] = [0]

        def _next(r: Request) -> Response:
            """Handle next."""
            call_count[0] += 1
            return Response(status_code=401 if call_count[0] == 1 else 200, content=b"")

        resp = auth.handle(req, _next)
        assert resp.status_code == 200
        assert call_count[0] == 2


# ---------------------------------------------------------------------------
# OAuth2 token_cache — pluggable backend tests
# ---------------------------------------------------------------------------


class TestOAuth2TokenCache:
    """Test suite for OAuth2TokenCache."""

    def test_shared_cache_fetches_token_once_across_instances(self) -> None:
        """Two instances sharing a LocMemCache fetch the token only once."""
        fetch_count: list[int] = [0]

        class _CountingTransport(SyncTransport):
            """Represent CountingTransport."""

            def send(self, request: Request) -> Response:
                """Return send."""
                fetch_count[0] += 1
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": "shared-token", "expires_in": 3600}
                    ).encode(),
                )

        shared_cache = LocMemCache()
        auth_a = OAuth2ClientCredentialsMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
            token_cache=shared_cache,
        )
        auth_b = OAuth2ClientCredentialsMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
            token_cache=shared_cache,
        )
        auth_a._transport = _CountingTransport()
        auth_b._transport = _CountingTransport()

        auth_a._get_token_header()  # populates shared cache
        auth_b._get_token_header()  # should hit shared cache, not fetch

        assert fetch_count[0] == 1

    def test_private_caches_fetch_independently(self) -> None:
        """Two instances with separate caches each fetch their own token."""
        fetch_count: list[int] = [0]

        class _CountingTransport(SyncTransport):
            """Represent CountingTransport."""

            def send(self, request: Request) -> Response:
                """Return send."""
                fetch_count[0] += 1
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": "tok", "expires_in": 3600}
                    ).encode(),
                )

        auth_a = OAuth2ClientCredentialsMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
        )
        auth_b = OAuth2ClientCredentialsMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
        )
        auth_a._transport = _CountingTransport()
        auth_b._transport = _CountingTransport()

        auth_a._get_token_header()
        auth_b._get_token_header()

        assert fetch_count[0] == 2

    def test_invalidate_removes_from_shared_cache(self) -> None:
        """Invalidating one instance also clears the shared cache entry."""
        fetch_count: list[int] = [0]

        class _CountingTransport(SyncTransport):
            """Represent CountingTransport."""

            def send(self, request: Request) -> Response:
                """Return send."""
                fetch_count[0] += 1
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": f"tok-{fetch_count[0]}", "expires_in": 3600}
                    ).encode(),
                )

        shared_cache = LocMemCache()
        auth_a = OAuth2ClientCredentialsMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
            token_cache=shared_cache,
        )
        auth_b = OAuth2ClientCredentialsMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
            token_cache=shared_cache,
        )
        transport = _CountingTransport()
        auth_a._transport = transport
        auth_b._transport = transport

        auth_a._get_token_header()  # fetch #1
        auth_a._invalidate()  # clears shared cache
        auth_b._get_token_header()  # must fetch again (#2)

        assert fetch_count[0] == 2


# ---------------------------------------------------------------------------
# AsyncOAuth2AuthMiddlewareBase — abstract contract
# ---------------------------------------------------------------------------


class TestAsyncOAuth2AuthMiddlewareBase:
    """Test suite for AsyncOAuth2AuthMiddlewareBase."""

    def test_cannot_instantiate_directly(self) -> None:
        """Validate cannot instantiate directly."""
        with pytest.raises(TypeError):
            AsyncOAuth2AuthMiddlewareBase(  # type: ignore[abstract]
                token_url=DUMMY_TOKEN_URL,
            )

    def test_async_oauth2auth_middleware_is_alias(self) -> None:
        """Validate async oauth2auth middleware is alias."""
        assert AsyncOAuth2AuthMiddleware is AsyncOAuth2ClientCredentialsMiddleware

    def test_client_credentials_is_subclass_of_base(self) -> None:
        """Validate client credentials is subclass of base."""
        assert issubclass(
            AsyncOAuth2ClientCredentialsMiddleware, AsyncOAuth2AuthMiddlewareBase
        )

    def test_password_is_subclass_of_base(self) -> None:
        """Validate password is subclass of base."""
        assert issubclass(AsyncOAuth2PasswordMiddleware, AsyncOAuth2AuthMiddlewareBase)


# ---------------------------------------------------------------------------
# AsyncOAuth2PasswordMiddleware
# ---------------------------------------------------------------------------


class TestAsyncOAuth2PasswordMiddleware:
    """Test suite for AsyncOAuth2PasswordMiddleware."""

    _USERNAME = "alice"
    _PASSWORD = "s3cr3t"

    def _make_auth(
        self,
        oauth_settings: _OAuthTestSettings,
        token_transport: _FakeAsyncTokenTransport,
        **kwargs: Any,
    ) -> AsyncOAuth2PasswordMiddleware:
        """Handle make auth."""
        auth = AsyncOAuth2PasswordMiddleware(
            client_id=oauth_settings.client_id,
            client_secret=oauth_settings.client_secret,
            token_url=oauth_settings.token_url,
            username=self._USERNAME,
            password=self._PASSWORD,
            **kwargs,
        )
        auth._transport = token_transport
        return auth

    async def test_get_token_header_returns_bearer_header(
        self,
        oauth_settings: _OAuthTestSettings,
        async_token_transport: _FakeAsyncTokenTransport,
    ) -> None:
        """Validate get token header returns bearer header."""
        auth = self._make_auth(oauth_settings, async_token_transport)
        headers = await auth._get_token_header()
        assert headers == {"Authorization": f"Bearer {DUMMY_ACCESS_TOKEN}"}
        assert async_token_transport.calls == 1

    async def test_token_is_cached_between_calls(
        self,
        oauth_settings: _OAuthTestSettings,
        async_token_transport: _FakeAsyncTokenTransport,
    ) -> None:
        """Validate token is cached between calls."""
        auth = self._make_auth(oauth_settings, async_token_transport)
        await auth._get_token_header()
        await auth._get_token_header()
        assert async_token_transport.calls == 1

    async def test_token_body_contains_grant_type_password(
        self, oauth_settings: _OAuthTestSettings
    ) -> None:
        """Validate token body contains grant type password."""
        seen_body: list[bytes] = []

        class _CapturingAsyncTransport(AsyncTransport):
            """Represent CapturingAsyncTransport."""

            async def send(self, request: Request) -> Response:
                """Return send."""
                seen_body.append(request.content or b"")
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": "t", "expires_in": 60}
                    ).encode(),
                )

        auth = AsyncOAuth2PasswordMiddleware(
            client_id="my-client",
            client_secret="my-secret",
            token_url=DUMMY_TOKEN_URL,
            username=self._USERNAME,
            password=self._PASSWORD,
        )
        auth._transport = _CapturingAsyncTransport()
        await auth._get_token_header()

        assert seen_body
        body_str = seen_body[0].decode()
        assert "grant_type=password" in body_str
        assert "client_id=my-client" in body_str
        assert f"username={self._USERNAME}" in body_str
        assert f"password={self._PASSWORD}" in body_str

    async def test_internal_transport_is_httpx_async(
        self, oauth_settings: _OAuthTestSettings
    ) -> None:
        """Validate internal transport is httpx2 async."""
        auth = AsyncOAuth2PasswordMiddleware(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            token_url=DUMMY_TOKEN_URL,
            username=self._USERNAME,
            password=self._PASSWORD,
        )
        assert isinstance(auth._transport, HttpxAsyncTransport)

    async def test_handle_retries_on_401(
        self,
        oauth_settings: _OAuthTestSettings,
        async_token_transport: _FakeAsyncTokenTransport,
    ) -> None:
        """Validate handle retries on 401."""
        auth = self._make_auth(oauth_settings, async_token_transport)
        req = Request(method="GET", url="https://example.com")
        call_count: list[int] = [0]

        async def _next(r: Request) -> Response:
            """Handle next."""
            call_count[0] += 1
            return Response(status_code=401 if call_count[0] == 1 else 200, content=b"")

        resp = await auth.handle(req, _next)
        assert resp.status_code == 200
        assert call_count[0] == 2


# ---------------------------------------------------------------------------
# OAuth2JWTBearerMiddleware (sync)
# ---------------------------------------------------------------------------


class TestOAuth2JWTBearerMiddleware:
    """Test suite for OAuth2JWTBearerMiddleware."""

    def test_token_body_contains_rfc7523_grant_type_and_assertion(self) -> None:
        """Validate request body matches RFC7523 parameters."""
        seen_body: list[bytes] = []

        class _CapturingTransport(SyncTransport):
            """Represent CapturingTransport."""

            def send(self, request: Request) -> Response:
                """Return send."""
                seen_body.append(request.content or b"")
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": "jwt-token", "expires_in": 60}
                    ).encode(),
                )

        auth = OAuth2JWTBearerMiddleware(
            token_url=DUMMY_TOKEN_URL,
            assertion_factory=lambda: "signed.jwt.assertion",
            cache_key_material="issuer:user",
        )
        auth._transport = _CapturingTransport()
        auth._get_token_header()

        assert seen_body
        body = seen_body[0].decode()
        assert (
            "grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer" in body
        )
        assert "assertion=signed.jwt.assertion" in body

    def test_optional_scope_is_added_to_token_request(self) -> None:
        """Validate optional scope is serialized when provided."""
        seen_body: list[bytes] = []

        class _CapturingTransport(SyncTransport):
            """Represent CapturingTransport."""

            def send(self, request: Request) -> Response:
                """Return send."""
                seen_body.append(request.content or b"")
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": "jwt-token", "expires_in": 60}
                    ).encode(),
                )

        auth = OAuth2JWTBearerMiddleware(
            token_url=DUMMY_TOKEN_URL,
            assertion_factory=lambda: "signed.jwt.assertion",
            cache_key_material="issuer:user",
            scope="api refresh_token",
        )
        auth._transport = _CapturingTransport()
        auth._get_token_header()

        assert seen_body
        assert "scope=api+refresh_token" in seen_body[0].decode()

    def test_empty_assertion_raises_value_error(self) -> None:
        """Validate empty assertions are rejected before HTTP I/O."""
        auth = OAuth2JWTBearerMiddleware(
            token_url=DUMMY_TOKEN_URL,
            assertion_factory=lambda: "",
            cache_key_material="issuer:user",
        )

        with pytest.raises(ValueError, match="empty JWT assertion"):
            auth._build_token_body()

    def test_non_string_assertion_raises_type_error(self) -> None:
        """Validate non-string assertion values are rejected."""
        auth = OAuth2JWTBearerMiddleware(
            token_url=DUMMY_TOKEN_URL,
            assertion_factory=cast(Callable[[], str], lambda: 123),
            cache_key_material="issuer:user",
        )

        with pytest.raises(TypeError, match="must return a JWT assertion string"):
            auth._build_token_body()

    def test_cache_key_uses_cache_key_material(self) -> None:
        """Different cache key materials produce different token cache keys."""
        auth_a = OAuth2JWTBearerMiddleware(
            token_url=DUMMY_TOKEN_URL,
            assertion_factory=lambda: "assertion-a",
            cache_key_material="issuer:user-a",
        )
        auth_b = OAuth2JWTBearerMiddleware(
            token_url=DUMMY_TOKEN_URL,
            assertion_factory=lambda: "assertion-b",
            cache_key_material="issuer:user-b",
        )

        assert auth_a._cache_key != auth_b._cache_key


# ---------------------------------------------------------------------------
# AsyncOAuth2JWTBearerMiddleware
# ---------------------------------------------------------------------------


class TestAsyncOAuth2JWTBearerMiddleware:
    """Test suite for AsyncOAuth2JWTBearerMiddleware."""

    async def test_token_body_contains_rfc7523_grant_type_and_assertion(
        self,
    ) -> None:
        """Validate async request body matches RFC7523 parameters."""
        seen_body: list[bytes] = []

        class _CapturingAsyncTransport(AsyncTransport):
            """Represent CapturingAsyncTransport."""

            async def send(self, request: Request) -> Response:
                """Return send."""
                seen_body.append(request.content or b"")
                return Response(
                    status_code=200,
                    content=json.dumps(
                        {"access_token": "jwt-token", "expires_in": 60}
                    ).encode(),
                )

        auth = AsyncOAuth2JWTBearerMiddleware(
            token_url=DUMMY_TOKEN_URL,
            assertion_factory=lambda: "signed.jwt.assertion",
            cache_key_material="issuer:user",
        )
        auth._transport = _CapturingAsyncTransport()
        await auth._get_token_header()

        assert seen_body
        body = seen_body[0].decode()
        assert (
            "grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer" in body
        )
        assert "assertion=signed.jwt.assertion" in body

    async def test_empty_assertion_raises_value_error(self) -> None:
        """Validate async middleware rejects empty assertions."""
        auth = AsyncOAuth2JWTBearerMiddleware(
            token_url=DUMMY_TOKEN_URL,
            assertion_factory=lambda: "",
            cache_key_material="issuer:user",
        )

        with pytest.raises(ValueError, match="empty JWT assertion"):
            auth._build_token_body()

    async def test_non_string_assertion_raises_type_error(self) -> None:
        """Validate async middleware rejects non-string assertions."""
        auth = AsyncOAuth2JWTBearerMiddleware(
            token_url=DUMMY_TOKEN_URL,
            assertion_factory=cast(Callable[[], str], lambda: 123),
            cache_key_material="issuer:user",
        )

        with pytest.raises(TypeError, match="must return a JWT assertion string"):
            auth._build_token_body()
