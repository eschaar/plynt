"""Cover Salesforce auth middleware behavior for sync and async flows."""

# Tests intentionally call protected auth hooks to verify cache/retry behavior.
# pyright: reportPrivateUsage=false
# pylint: disable=protected-access,redefined-outer-name,unused-argument

from __future__ import annotations

import time
from typing import Any, Literal, overload
from urllib.parse import parse_qs

import jwt as pyjwt
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from plynth.base.request import Request
from plynth.base.response import Response
from plynth.base.transport import AsyncTransport, SyncTransport
from plynth.connectors.salesforce.auth import (
    AsyncSalesforceClientCredentialsAuthMiddleware,
    AsyncSalesforceJWTBearerAuthMiddleware,
    AsyncSalesforcePasswordAuthMiddleware,
    AsyncSalesforceSessionAuthMiddleware,
    SalesforceClientCredentialsAuthMiddleware,
    SalesforceJWTBearerAuthMiddleware,
    SalesforcePasswordAuthMiddleware,
    SalesforceSessionAuthMiddleware,
)
from plynth.connectors.salesforce.auth.service import _build_jwt_assertion
from tests.connectors.salesforce.conftest import (
    DUMMY_ACCESS_TOKEN,
    DUMMY_CLIENT_ID,
    DUMMY_CLIENT_SECRET,
    DUMMY_INSTANCE_URL,
    DUMMY_PASSWORD,
    DUMMY_TOKEN_URL,
    DUMMY_USERNAME,
    FakeAsyncSalesforceTokenTransport,
    FakeSalesforceTokenTransport,
    render_json_bytes,
)

# ---------------------------------------------------------------------------
# Client credentials (sync)
# ---------------------------------------------------------------------------


class TestSalesforceClientCredentialsAuthMiddleware:
    """Exercise sync client-credentials auth and instance_url caching behavior."""

    def test_instance_url_is_extracted_from_token_response(self) -> None:
        """Token response from Salesforce populates instance_url on the middleware."""
        auth = _make_auth()
        assert auth.instance_url == DUMMY_INSTANCE_URL

    def test_instance_url_triggers_token_fetch(self) -> None:
        """Accessing instance_url triggers exactly one token request."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_auth(transport)
        _ = auth.instance_url
        assert transport.calls == 1

    def test_instance_url_is_cached_alongside_token(self) -> None:
        """Repeated instance_url access uses the cached token without re-fetching."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_auth(transport)
        _ = auth.instance_url
        _ = auth.instance_url
        assert transport.calls == 1

    def test_access_token_and_instance_url_fetched_in_single_request(self) -> None:
        """Both the access token header and instance_url come from a single request."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_auth(transport)
        headers = auth._get_token_header()
        assert headers == {"Authorization": f"Bearer {DUMMY_ACCESS_TOKEN}"}
        assert auth.instance_url == DUMMY_INSTANCE_URL
        assert transport.calls == 1

    def test_invalidate_clears_instance_url_cache(self) -> None:
        """Calling _invalidate() forces a new token request on the next access."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_auth(transport)
        _ = auth.instance_url
        auth._invalidate()
        _ = auth.instance_url
        assert transport.calls == 2

    def test_instance_url_updated_after_invalidate(self) -> None:
        """After invalidation, the new instance_url reflects the latest response."""
        new_instance_url = "https://neworg.my.salesforce.com"

        class _RotatingTransport(SyncTransport):
            """Return different instance_url values across subsequent token calls."""

            calls: int = 0

            def send(self, request: Request) -> Response:
                """Return a token response whose instance_url rotates per call."""
                self.calls += 1
                url = DUMMY_INSTANCE_URL if self.calls == 1 else new_instance_url
                body = render_json_bytes(
                    {
                        "access_token": f"token-{self.calls}",
                        "expires_in": 3600,
                        "instance_url": url,
                    }
                )
                return Response(status_code=200, content=body)

        transport = _RotatingTransport()
        auth = _make_auth(transport)
        assert auth.instance_url == DUMMY_INSTANCE_URL
        auth._invalidate()
        assert auth.instance_url == new_instance_url

    def test_missing_instance_url_raises_runtime_error(self) -> None:
        """Token response without instance_url field raises RuntimeError on access."""
        transport = FakeSalesforceTokenTransport(include_instance_url=False)
        auth = _make_auth(transport)
        with pytest.raises(RuntimeError, match="instance_url"):
            _ = auth.instance_url

    def test_empty_instance_url_raises_runtime_error(self) -> None:
        """Token response with empty instance_url raises RuntimeError on access."""
        transport = FakeSalesforceTokenTransport(instance_url="")
        auth = _make_auth(transport)
        with pytest.raises(RuntimeError, match="instance_url"):
            _ = auth.instance_url

    def test_authenticate_also_caches_instance_url(self) -> None:
        """Calling _get_token_header() first means instance_url returns from cache."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_auth(transport)
        auth._get_token_header()
        _ = auth.instance_url
        assert transport.calls == 1

    def test_error_response_raises_runtime_error(self) -> None:
        """Non-2xx token response raises RuntimeError including the status code."""
        transport = FakeSalesforceTokenTransport(status=401)
        auth = _make_auth(transport)
        with pytest.raises(RuntimeError, match="401"):
            _ = auth.instance_url

    def test_client_credentials_flow_sends_expected_form_fields(self) -> None:
        """Validate token form has grant_type, client_id, and client_secret."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_auth(transport)
        _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["grant_type"] == ["client_credentials"]
        assert params["client_id"] == [DUMMY_CLIENT_ID]
        assert params["client_secret"] == [DUMMY_CLIENT_SECRET]


class TestSalesforcePasswordAuthMiddleware:
    """Exercise sync password auth payload construction and token variants."""

    def test_instance_url_is_extracted_from_token_response(self) -> None:
        """Token response from Salesforce populates instance_url on the middleware."""
        auth = _make_auth(flow="password")
        assert auth.instance_url == DUMMY_INSTANCE_URL

    def test_password_flow_sends_expected_form_fields(self) -> None:
        """Validate token form has grant_type, username, and password."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_auth(transport, flow="password")
        _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["grant_type"] == ["password"]
        assert params["client_id"] == [DUMMY_CLIENT_ID]
        assert params["client_secret"] == [DUMMY_CLIENT_SECRET]
        assert params["username"] == [DUMMY_USERNAME]
        assert params["password"] == [DUMMY_PASSWORD]

    def test_password_flow_appends_security_token_to_password(self) -> None:
        """Validate password field appends the Salesforce security token."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_auth(transport, flow="password", security_token="MYTOKEN")
        _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["password"] == [DUMMY_PASSWORD + "MYTOKEN"]

    def test_password_flow_keeps_password_when_security_token_is_empty(self) -> None:
        """Validate password remains unchanged when security_token is empty."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_auth(transport, flow="password", security_token="")
        _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["password"] == [DUMMY_PASSWORD]


class TestSalesforceSessionAuthMiddleware:
    """Exercise direct session/token middleware variants."""

    def test_sync_session_middleware_sets_authorization_header(self) -> None:
        """Validate sync middleware injects bearer header from access token."""
        auth = SalesforceSessionAuthMiddleware(
            access_token=DUMMY_ACCESS_TOKEN,
            instance_url=DUMMY_INSTANCE_URL,
        )
        request = Request(method="GET", url="https://example.com", headers={})

        def _next(req: Request) -> Response:
            """Return next response."""
            return Response(status_code=200, headers=req.headers)

        response = auth.handle(request, _next)
        assert response.headers["Authorization"] == f"Bearer {DUMMY_ACCESS_TOKEN}"
        assert auth.instance_url == DUMMY_INSTANCE_URL

    async def test_async_session_middleware_exposes_instance_url(self) -> None:
        """Validate async middleware keeps and exposes configured instance URL."""
        auth = AsyncSalesforceSessionAuthMiddleware(
            access_token=DUMMY_ACCESS_TOKEN,
            instance_url=DUMMY_INSTANCE_URL,
        )
        assert await auth.get_instance_url() == DUMMY_INSTANCE_URL


# ---------------------------------------------------------------------------
# Auth middleware factory
# ---------------------------------------------------------------------------

_FLOW = Literal["client_credentials", "password"]

_CLS_MAP: dict[tuple[str, bool], Any] = {
    ("client_credentials", False): SalesforceClientCredentialsAuthMiddleware,
    ("password", False): SalesforcePasswordAuthMiddleware,
    ("client_credentials", True): AsyncSalesforceClientCredentialsAuthMiddleware,
    ("password", True): AsyncSalesforcePasswordAuthMiddleware,
}


def _inject_token_transport(
    auth: object,
    transport: SyncTransport | AsyncTransport,
) -> None:
    """Inject fake token transport to isolate middleware behavior in tests."""
    object.__setattr__(auth, "_transport", transport)


@overload
def _make_auth(
    transport: SyncTransport | None = ...,
    *,
    flow: Literal["client_credentials"] = ...,
    async_mode: Literal[False] = ...,
    **kwargs: object,
) -> SalesforceClientCredentialsAuthMiddleware: ...


@overload
def _make_auth(
    transport: SyncTransport | None = ...,
    *,
    flow: Literal["password"],
    async_mode: Literal[False] = ...,
    **kwargs: object,
) -> SalesforcePasswordAuthMiddleware: ...


@overload
def _make_auth(
    transport: AsyncTransport | None = ...,
    *,
    flow: Literal["client_credentials"] = ...,
    async_mode: Literal[True],
    **kwargs: object,
) -> AsyncSalesforceClientCredentialsAuthMiddleware: ...


@overload
def _make_auth(
    transport: AsyncTransport | None = ...,
    *,
    flow: Literal["password"],
    async_mode: Literal[True],
    **kwargs: object,
) -> AsyncSalesforcePasswordAuthMiddleware: ...


def _make_auth(
    transport: SyncTransport | AsyncTransport | None = None,
    *,
    flow: str = "client_credentials",
    async_mode: bool = False,
    **kwargs: object,
) -> Any:
    """Build Salesforce auth middleware wired to a deterministic test transport.

    Args:
        transport: Optional sync or async transport stub. A default fake
            is used when omitted.
        flow: Auth grant type — ``"client_credentials"`` (default) or
            ``"password"``. Extend ``_CLS_MAP`` to support future flows.
        async_mode: When ``True``, returns the async middleware variant.
        **kwargs: Extra arguments forwarded to the middleware constructor
            (e.g. ``security_token``, ``ttl_leeway``, ``include_instance_url``).

    """
    base: dict[str, object] = {
        "client_id": DUMMY_CLIENT_ID,
        "client_secret": DUMMY_CLIENT_SECRET,
        "token_url": DUMMY_TOKEN_URL,
    }
    if flow == "password":
        base.setdefault("username", DUMMY_USERNAME)
        base.setdefault("password", DUMMY_PASSWORD)
    auth = _CLS_MAP[(flow, async_mode)](**{**base, **kwargs})
    injected_transport = transport or (
        FakeAsyncSalesforceTokenTransport()
        if async_mode
        else FakeSalesforceTokenTransport()
    )
    _inject_token_transport(auth, injected_transport)
    return auth


# ---------------------------------------------------------------------------
# Client credentials (async)
# ---------------------------------------------------------------------------


class TestAsyncSalesforceClientCredentialsAuthMiddleware:
    """Exercise async client-credentials auth and instance_url caching behavior."""

    async def test_get_instance_url_returns_instance_url(self) -> None:
        """Token response from Salesforce populates instance_url on the middleware."""
        auth = _make_auth(async_mode=True)
        assert await auth.get_instance_url() == DUMMY_INSTANCE_URL

    async def test_get_instance_url_triggers_token_fetch(self) -> None:
        """Calling get_instance_url() triggers exactly one token request."""
        transport = FakeAsyncSalesforceTokenTransport()
        auth = _make_auth(transport, async_mode=True)
        await auth.get_instance_url()
        assert transport.calls == 1

    async def test_get_instance_url_is_cached_alongside_token(self) -> None:
        """Repeated get_instance_url() calls reuse the cached token."""
        transport = FakeAsyncSalesforceTokenTransport()
        auth = _make_auth(transport, async_mode=True)
        await auth.get_instance_url()
        await auth.get_instance_url()
        assert transport.calls == 1

    async def test_token_header_and_instance_url_fetched_in_single_request(
        self,
    ) -> None:
        """Both the access token header and instance_url come from a single request."""
        transport = FakeAsyncSalesforceTokenTransport()
        auth = _make_auth(transport, async_mode=True)
        headers = await auth._get_token_header()
        assert headers == {"Authorization": f"Bearer {DUMMY_ACCESS_TOKEN}"}
        assert await auth.get_instance_url() == DUMMY_INSTANCE_URL
        assert transport.calls == 1

    async def test_invalidate_clears_instance_url_cache(self) -> None:
        """Calling _invalidate() forces a new token request on the next access."""
        transport = FakeAsyncSalesforceTokenTransport()
        auth = _make_auth(transport, async_mode=True)
        await auth.get_instance_url()
        auth._invalidate()
        await auth.get_instance_url()
        assert transport.calls == 2

    async def test_instance_url_updated_after_invalidate(self) -> None:
        """After _invalidate(), get_instance_url() reflects the new token response."""
        new_instance_url = "https://neworg.my.salesforce.com"

        class _RotatingAsyncTransport(AsyncTransport):
            """Return different instance_url values across subsequent token calls."""

            calls: int = 0

            async def send(self, request: Request) -> Response:
                """Return a token response whose instance_url rotates per call."""
                self.calls += 1
                url = DUMMY_INSTANCE_URL if self.calls == 1 else new_instance_url
                body = render_json_bytes(
                    {
                        "access_token": f"token-{self.calls}",
                        "expires_in": 3600,
                        "instance_url": url,
                    }
                )
                return Response(status_code=200, content=body)

        transport = _RotatingAsyncTransport()
        auth = _make_auth(transport, async_mode=True)
        assert await auth.get_instance_url() == DUMMY_INSTANCE_URL
        auth._invalidate()
        assert await auth.get_instance_url() == new_instance_url

    async def test_missing_instance_url_raises_runtime_error(self) -> None:
        """Token response without instance_url field raises RuntimeError on access."""
        transport = FakeAsyncSalesforceTokenTransport(include_instance_url=False)
        auth = _make_auth(transport, async_mode=True)
        with pytest.raises(RuntimeError, match="instance_url"):
            await auth.get_instance_url()

    async def test_empty_instance_url_raises_runtime_error(self) -> None:
        """Token response with empty instance_url raises RuntimeError on access."""
        transport = FakeAsyncSalesforceTokenTransport(instance_url="")
        auth = _make_auth(transport, async_mode=True)
        with pytest.raises(RuntimeError, match="instance_url"):
            await auth.get_instance_url()

    async def test_authenticate_also_caches_instance_url(self) -> None:
        """Calling _get_token_header() first means get_instance_url hits the cache."""
        transport = FakeAsyncSalesforceTokenTransport()
        auth = _make_auth(transport, async_mode=True)
        await auth._get_token_header()
        await auth.get_instance_url()
        assert transport.calls == 1

    async def test_error_response_raises_runtime_error(self) -> None:
        """Non-2xx token response raises RuntimeError including the status code."""
        transport = FakeAsyncSalesforceTokenTransport(status=401)
        auth = _make_auth(transport, async_mode=True)
        with pytest.raises(RuntimeError, match="401"):
            await auth.get_instance_url()

    async def test_client_credentials_flow_sends_expected_form_fields(self) -> None:
        """Validate token form has grant_type, client_id, and client_secret."""
        transport = FakeAsyncSalesforceTokenTransport()
        auth = _make_auth(transport, async_mode=True)
        await auth.get_instance_url()
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["grant_type"] == ["client_credentials"]
        assert params["client_id"] == [DUMMY_CLIENT_ID]
        assert params["client_secret"] == [DUMMY_CLIENT_SECRET]


class TestAsyncSalesforcePasswordAuthMiddleware:
    """Exercise async password auth payload construction and token variants."""

    async def test_get_instance_url_returns_instance_url(self) -> None:
        """Token response from Salesforce populates instance_url on the middleware."""
        auth = _make_auth(flow="password", async_mode=True)
        assert await auth.get_instance_url() == DUMMY_INSTANCE_URL

    async def test_password_flow_sends_expected_form_fields(self) -> None:
        """Validate token form has grant_type, username, and password."""
        transport = FakeAsyncSalesforceTokenTransport()
        auth = _make_auth(transport, flow="password", async_mode=True)
        await auth.get_instance_url()
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["grant_type"] == ["password"]
        assert params["client_id"] == [DUMMY_CLIENT_ID]
        assert params["client_secret"] == [DUMMY_CLIENT_SECRET]
        assert params["username"] == [DUMMY_USERNAME]
        assert params["password"] == [DUMMY_PASSWORD]

    async def test_password_flow_appends_security_token_to_password(self) -> None:
        """Validate password field appends the Salesforce security token."""
        transport = FakeAsyncSalesforceTokenTransport()
        auth = _make_auth(
            transport, flow="password", async_mode=True, security_token="MYTOKEN"
        )
        await auth.get_instance_url()
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["password"] == [DUMMY_PASSWORD + "MYTOKEN"]

    async def test_password_flow_keeps_password_when_security_token_is_empty(
        self,
    ) -> None:
        """Validate password remains unchanged when security_token is empty."""
        transport = FakeAsyncSalesforceTokenTransport()
        auth = _make_auth(
            transport, flow="password", async_mode=True, security_token=""
        )
        await auth.get_instance_url()
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["password"] == [DUMMY_PASSWORD]


# ---------------------------------------------------------------------------
# JWT Bearer helpers
# ---------------------------------------------------------------------------


def _generate_rsa_private_key_pem() -> str:
    """Generate a throwaway RSA-2048 private key in PEM format."""
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


DUMMY_PRIVATE_KEY = _generate_rsa_private_key_pem()
DUMMY_JWT_USERNAME = "integration@myorg.com"


@overload
def _make_jwt_auth(
    transport: SyncTransport | None = ...,
    *,
    async_mode: Literal[False] = ...,
    **kwargs: object,
) -> SalesforceJWTBearerAuthMiddleware: ...


@overload
def _make_jwt_auth(
    transport: AsyncTransport | None = ...,
    *,
    async_mode: Literal[True],
    **kwargs: object,
) -> AsyncSalesforceJWTBearerAuthMiddleware: ...


def _make_jwt_auth(
    transport: SyncTransport | AsyncTransport | None = None,
    *,
    async_mode: bool = False,
    **kwargs: object,
) -> SalesforceJWTBearerAuthMiddleware | AsyncSalesforceJWTBearerAuthMiddleware:
    """Build JWT bearer auth middleware wired to deterministic test transport."""
    base: dict[str, object] = {
        "client_id": DUMMY_CLIENT_ID,
        "username": DUMMY_JWT_USERNAME,
        "private_key": DUMMY_PRIVATE_KEY,
        "token_url": DUMMY_TOKEN_URL,
    }
    if async_mode:
        auth_async = AsyncSalesforceJWTBearerAuthMiddleware(**{**base, **kwargs})  # type: ignore[arg-type]
        injected_async_transport = (
            transport
            if isinstance(transport, AsyncTransport)
            else FakeAsyncSalesforceTokenTransport()
        )
        _inject_token_transport(auth_async, injected_async_transport)
        return auth_async

    auth_sync = SalesforceJWTBearerAuthMiddleware(**{**base, **kwargs})  # type: ignore[arg-type]
    injected_sync_transport = (
        transport
        if isinstance(transport, SyncTransport)
        else FakeSalesforceTokenTransport()
    )
    _inject_token_transport(auth_sync, injected_sync_transport)
    return auth_sync


# ---------------------------------------------------------------------------
# JWT Bearer — sync
# ---------------------------------------------------------------------------


class TestSalesforceJWTBearerAuthMiddleware:
    """Exercise sync JWT bearer assertion, audience, expiry, and retry behavior."""

    def test_instance_url_extracted_from_token_response(self) -> None:
        """Token response from Salesforce populates instance_url on the middleware."""
        auth = _make_jwt_auth()
        assert auth.instance_url == DUMMY_INSTANCE_URL

    def test_token_fetched_once_for_multiple_instance_url_calls(self) -> None:
        """Repeated instance_url access uses the cached token without re-fetching."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_jwt_auth(transport)
        _ = auth.instance_url
        _ = auth.instance_url
        assert transport.calls == 1

    def test_jwt_bearer_flow_sends_rfc7523_grant_type(self) -> None:
        """Validate grant_type is the RFC7523 JWT bearer URN."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_jwt_auth(transport)
        _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["grant_type"] == ["urn:ietf:params:oauth:grant-type:jwt-bearer"]

    def test_jwt_bearer_flow_builds_rs256_assertion_with_expected_claims(self) -> None:
        """Validate JWT assertion carries expected iss/sub/aud and exp claims."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_jwt_auth(transport)
        _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assertion = params["assertion"][0]

        # Decode without verifying signature to inspect claims structure
        header = pyjwt.get_unverified_header(assertion)
        assert header["alg"] == "RS256"

        payload = pyjwt.decode(
            assertion,
            options={"verify_signature": False},
        )
        assert payload["iss"] == DUMMY_CLIENT_ID
        assert payload["sub"] == DUMMY_JWT_USERNAME
        assert payload["aud"] == "https://login.salesforce.com"
        assert "exp" in payload

    def test_jwt_audience_uses_scheme_and_host_from_token_url(self) -> None:
        """Validate aud claim is derived from token_url scheme and host."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_jwt_auth(
            transport,
            token_url="https://test.salesforce.com/services/oauth2/token",
        )
        _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        payload = pyjwt.decode(
            params["assertion"][0], options={"verify_signature": False}
        )
        assert payload["aud"] == "https://test.salesforce.com"

    def test_jwt_exp_claim_respects_configured_expiry_window(self) -> None:
        """Validate exp claim falls within the configured jwt_exp_seconds window."""
        exp_seconds = 120
        transport = FakeSalesforceTokenTransport()
        auth = _make_jwt_auth(transport, jwt_exp_seconds=exp_seconds)
        before = int(time.time())
        _ = auth.instance_url
        after = int(time.time())
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        payload = pyjwt.decode(
            params["assertion"][0], options={"verify_signature": False}
        )
        assert before + exp_seconds <= payload["exp"] <= after + exp_seconds

    def test_jwt_bearer_flow_includes_optional_scope_when_configured(self) -> None:
        """Validate optional scope is serialized into the JWT bearer request."""
        transport = FakeSalesforceTokenTransport()
        auth = _make_jwt_auth(transport, scope="api refresh_token")
        _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["scope"] == ["api refresh_token"]

    def test_raises_on_exp_seconds_above_max(self) -> None:
        """jwt_exp_seconds > 300 is rejected at construction (Salesforce cap)."""
        with pytest.raises(ValueError, match="jwt_exp_seconds"):
            SalesforceJWTBearerAuthMiddleware(
                client_id=DUMMY_CLIENT_ID,
                username=DUMMY_JWT_USERNAME,
                private_key=DUMMY_PRIVATE_KEY,
                token_url=DUMMY_TOKEN_URL,
                jwt_exp_seconds=301,
            )

    def test_raises_on_exp_seconds_below_min(self) -> None:
        """jwt_exp_seconds < 1 is rejected at construction (zero-lifetime guard)."""
        with pytest.raises(ValueError, match="jwt_exp_seconds"):
            SalesforceJWTBearerAuthMiddleware(
                client_id=DUMMY_CLIENT_ID,
                username=DUMMY_JWT_USERNAME,
                private_key=DUMMY_PRIVATE_KEY,
                token_url=DUMMY_TOKEN_URL,
                jwt_exp_seconds=0,
            )

    def test_non_string_jwt_assertion_raises_type_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Validate non-string JWT assertion values are rejected."""
        import jwt as jwt_module

        monkeypatch.setattr(jwt_module, "encode", lambda *args, **kwargs: 123)

        with pytest.raises(TypeError, match="unexpected token type"):
            auth = _make_jwt_auth()
            auth._get_token_header()

    def test_jwt_assertion_bytes_are_decoded_to_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Validate byte-returning JWT encoders are decoded to text."""
        import jwt as jwt_module

        monkeypatch.setattr(jwt_module, "encode", lambda *args, **kwargs: b"jwt-bytes")

        assertion = _build_jwt_assertion(
            client_id=DUMMY_CLIENT_ID,
            username=DUMMY_JWT_USERNAME,
            audience="https://login.salesforce.com",
            private_key=DUMMY_PRIVATE_KEY,
            exp_seconds=60,
        )

        assert assertion == "jwt-bytes"

    async def test_jwt_bearer_flow_includes_optional_scope_when_configured_async(
        self,
    ) -> None:
        """Validate optional scope is serialized into the JWT bearer request."""
        transport = FakeAsyncSalesforceTokenTransport()
        auth = _make_jwt_auth(transport, async_mode=True, scope="api refresh_token")
        await auth.get_instance_url()
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["scope"] == ["api refresh_token"]

    def test_downstream_401_invalidates_token_and_retries_once(self) -> None:
        """Validate first 401 invalidates token and refreshes once before retry."""
        token_transport = FakeSalesforceTokenTransport()
        auth = _make_jwt_auth(token_transport)

        call_count = 0

        def next_handler(_request: Request) -> Any:
            """Return a 401 on the first call, then 200, to simulate token expiry."""
            nonlocal call_count
            call_count += 1

            return Response(
                status_code=200 if call_count > 1 else 401,
                content=b"",
            )

        auth.handle(Request(method="GET", url="https://example.com"), next_handler)
        assert token_transport.calls == 2


# ---------------------------------------------------------------------------
# JWT Bearer — async
# ---------------------------------------------------------------------------


class TestAsyncSalesforceJWTBearerAuthMiddleware:
    """Exercise async JWT bearer assertion and boundary validation behavior."""

    async def test_instance_url_extracted_from_token_response(self) -> None:
        """Token response from Salesforce populates instance_url on the middleware."""
        auth = _make_jwt_auth(async_mode=True)
        assert await auth.get_instance_url() == DUMMY_INSTANCE_URL

    async def test_token_fetched_once_for_multiple_instance_url_calls(
        self,
    ) -> None:
        """Repeated get_instance_url() calls reuse the cached token."""
        transport = FakeAsyncSalesforceTokenTransport()
        auth = _make_jwt_auth(transport, async_mode=True)
        await auth.get_instance_url()
        await auth.get_instance_url()
        assert transport.calls == 1

    async def test_jwt_bearer_flow_sends_rfc7523_grant_type(self) -> None:
        """Validate grant_type is the RFC7523 JWT bearer URN."""
        transport = FakeAsyncSalesforceTokenTransport()
        auth = _make_jwt_auth(transport, async_mode=True)
        await auth.get_instance_url()
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["grant_type"] == ["urn:ietf:params:oauth:grant-type:jwt-bearer"]

    async def test_jwt_bearer_flow_builds_rs256_assertion_with_expected_claims(
        self,
    ) -> None:
        """Validate JWT assertion carries expected iss/sub/aud claims."""
        transport = FakeAsyncSalesforceTokenTransport()
        auth = _make_jwt_auth(transport, async_mode=True)
        await auth.get_instance_url()
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assertion = params["assertion"][0]
        header = pyjwt.get_unverified_header(assertion)
        assert header["alg"] == "RS256"
        payload = pyjwt.decode(assertion, options={"verify_signature": False})
        assert payload["iss"] == DUMMY_CLIENT_ID
        assert payload["sub"] == DUMMY_JWT_USERNAME
        assert payload["aud"] == "https://login.salesforce.com"

    async def test_raises_on_exp_seconds_above_max(self) -> None:
        """jwt_exp_seconds > 300 is rejected at construction (Salesforce cap)."""
        with pytest.raises(ValueError, match="jwt_exp_seconds"):
            AsyncSalesforceJWTBearerAuthMiddleware(
                client_id=DUMMY_CLIENT_ID,
                username=DUMMY_JWT_USERNAME,
                private_key=DUMMY_PRIVATE_KEY,
                token_url=DUMMY_TOKEN_URL,
                jwt_exp_seconds=301,
            )
