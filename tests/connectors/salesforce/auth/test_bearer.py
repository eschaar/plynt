"""Cover Salesforce JWT bearer auth middleware behavior."""

# Tests intentionally call protected auth hooks to verify cache/retry behavior.
# pyright: reportPrivateUsage=false
# pylint: disable=protected-access,redefined-outer-name,unused-argument

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs

import jwt as pyjwt
import pytest
import time_machine

from plynt.base.request import Request
from plynt.base.response import Response
from plynt.connectors.salesforce.auth import (
    AsyncSalesforceJWTBearerAuthMiddleware,
    SalesforceJWTBearerAuthMiddleware,
)
from plynt.connectors.salesforce.auth.bearer import _build_jwt_assertion
from tests.connectors.salesforce.auth.helpers import (
    DUMMY_JWT_USERNAME,
    DUMMY_PRIVATE_KEY,
    make_bearer_auth,
)
from tests.connectors.salesforce.conftest import (
    DUMMY_CLIENT_ID,
    DUMMY_INSTANCE_URL,
    DUMMY_TOKEN_URL,
    FakeAsyncSalesforceTokenTransport,
    FakeSalesforceTokenTransport,
)


class TestSalesforceJWTBearerAuthMiddleware:
    """Exercise sync JWT bearer assertion, audience, expiry, and retry behavior."""

    def test_instance_url_extracted_from_token_response(self) -> None:
        auth = make_bearer_auth()
        assert auth.instance_url == DUMMY_INSTANCE_URL

    def test_token_fetched_once_for_multiple_instance_url_calls(self) -> None:
        transport = FakeSalesforceTokenTransport()
        auth = make_bearer_auth(transport)
        _ = auth.instance_url
        _ = auth.instance_url
        assert transport.calls == 1

    def test_jwt_bearer_flow_sends_rfc7523_grant_type(self) -> None:
        transport = FakeSalesforceTokenTransport()
        auth = make_bearer_auth(transport)
        _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["grant_type"] == ["urn:ietf:params:oauth:grant-type:jwt-bearer"]

    def test_jwt_bearer_flow_builds_rs256_assertion_with_expected_claims(self) -> None:
        transport = FakeSalesforceTokenTransport()
        auth = make_bearer_auth(transport)
        _ = auth.instance_url
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
        assert "exp" in payload

    def test_jwt_audience_uses_scheme_and_host_from_token_url(self) -> None:
        transport = FakeSalesforceTokenTransport()
        auth = make_bearer_auth(
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
        exp_seconds = 120
        transport = FakeSalesforceTokenTransport()
        auth = make_bearer_auth(transport, jwt_exp_seconds=exp_seconds)
        fixed_now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        with time_machine.travel(fixed_now, tick=False):
            _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        payload = pyjwt.decode(
            params["assertion"][0], options={"verify_signature": False}
        )
        assert payload["exp"] == int(fixed_now.timestamp()) + exp_seconds

    def test_jwt_bearer_flow_includes_optional_scope_when_configured(self) -> None:
        transport = FakeSalesforceTokenTransport()
        auth = make_bearer_auth(transport, scope="api refresh_token")
        _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["scope"] == ["api refresh_token"]

    def test_raises_on_exp_seconds_above_max(self) -> None:
        with pytest.raises(ValueError, match="jwt_exp_seconds"):
            SalesforceJWTBearerAuthMiddleware(
                client_id=DUMMY_CLIENT_ID,
                username=DUMMY_JWT_USERNAME,
                private_key=DUMMY_PRIVATE_KEY,
                token_url=DUMMY_TOKEN_URL,
                jwt_exp_seconds=301,
            )

    def test_raises_on_exp_seconds_below_min(self) -> None:
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
        import jwt as jwt_module

        monkeypatch.setattr(jwt_module, "encode", lambda *args, **kwargs: 123)

        with pytest.raises(TypeError, match="unexpected token type"):
            auth = make_bearer_auth()
            auth._get_token_header()

    def test_jwt_assertion_bytes_are_decoded_to_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        transport = FakeAsyncSalesforceTokenTransport()
        auth = make_bearer_auth(
            transport,
            async_mode=True,
            scope="api refresh_token",
        )
        await auth.get_instance_url()
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["scope"] == ["api refresh_token"]

    def test_downstream_401_invalidates_token_and_retries_once(self) -> None:
        token_transport = FakeSalesforceTokenTransport()
        auth = make_bearer_auth(token_transport)

        call_count = 0

        def next_handler(_request: Request) -> Response:
            nonlocal call_count
            call_count += 1
            return Response(status_code=200 if call_count > 1 else 401, content=b"")

        auth.handle(Request(method="GET", url="https://example.com"), next_handler)
        assert token_transport.calls == 2


class TestAsyncSalesforceJWTBearerAuthMiddleware:
    """Exercise async JWT bearer assertion and boundary validation behavior."""

    async def test_instance_url_extracted_from_token_response(self) -> None:
        auth = make_bearer_auth(async_mode=True)
        assert await auth.get_instance_url() == DUMMY_INSTANCE_URL

    async def test_token_fetched_once_for_multiple_instance_url_calls(self) -> None:
        transport = FakeAsyncSalesforceTokenTransport()
        auth = make_bearer_auth(transport, async_mode=True)
        await auth.get_instance_url()
        await auth.get_instance_url()
        assert transport.calls == 1

    async def test_jwt_bearer_flow_sends_rfc7523_grant_type(self) -> None:
        transport = FakeAsyncSalesforceTokenTransport()
        auth = make_bearer_auth(transport, async_mode=True)
        await auth.get_instance_url()
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["grant_type"] == ["urn:ietf:params:oauth:grant-type:jwt-bearer"]

    async def test_jwt_bearer_flow_builds_rs256_assertion_with_expected_claims(
        self,
    ) -> None:
        transport = FakeAsyncSalesforceTokenTransport()
        auth = make_bearer_auth(transport, async_mode=True)
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
        with pytest.raises(ValueError, match="jwt_exp_seconds"):
            AsyncSalesforceJWTBearerAuthMiddleware(
                client_id=DUMMY_CLIENT_ID,
                username=DUMMY_JWT_USERNAME,
                private_key=DUMMY_PRIVATE_KEY,
                token_url=DUMMY_TOKEN_URL,
                jwt_exp_seconds=301,
            )
