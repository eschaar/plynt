"""Cover Salesforce password auth middleware behavior."""

from __future__ import annotations

from urllib.parse import parse_qs

from tests.connectors.salesforce.auth.support import make_auth
from tests.connectors.salesforce.conftest import (
    DUMMY_CLIENT_ID,
    DUMMY_CLIENT_SECRET,
    DUMMY_INSTANCE_URL,
    DUMMY_PASSWORD,
    DUMMY_USERNAME,
    FakeAsyncSalesforceTokenTransport,
    FakeSalesforceTokenTransport,
)


class TestSalesforcePasswordAuthMiddleware:
    """Exercise sync password auth payload construction and token variants."""

    def test_instance_url_is_extracted_from_token_response(self) -> None:
        auth = make_auth(flow="password")
        assert auth.instance_url == DUMMY_INSTANCE_URL

    def test_password_flow_sends_expected_form_fields(self) -> None:
        transport = FakeSalesforceTokenTransport()
        auth = make_auth(transport, flow="password")
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
        transport = FakeSalesforceTokenTransport()
        auth = make_auth(transport, flow="password", security_token="MYTOKEN")
        _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["password"] == [DUMMY_PASSWORD + "MYTOKEN"]

    def test_password_flow_keeps_password_when_security_token_is_empty(self) -> None:
        transport = FakeSalesforceTokenTransport()
        auth = make_auth(transport, flow="password", security_token="")
        _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["password"] == [DUMMY_PASSWORD]


class TestAsyncSalesforcePasswordAuthMiddleware:
    """Exercise async password auth payload construction and token variants."""

    async def test_get_instance_url_returns_instance_url(self) -> None:
        auth = make_auth(flow="password", async_mode=True)
        assert await auth.get_instance_url() == DUMMY_INSTANCE_URL

    async def test_password_flow_sends_expected_form_fields(self) -> None:
        transport = FakeAsyncSalesforceTokenTransport()
        auth = make_auth(transport, flow="password", async_mode=True)
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
        transport = FakeAsyncSalesforceTokenTransport()
        auth = make_auth(
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
        transport = FakeAsyncSalesforceTokenTransport()
        auth = make_auth(transport, flow="password", async_mode=True, security_token="")
        await auth.get_instance_url()
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["password"] == [DUMMY_PASSWORD]
