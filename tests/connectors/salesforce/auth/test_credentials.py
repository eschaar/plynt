"""Cover Salesforce client credentials auth middleware behavior."""

# Tests intentionally call protected auth hooks to verify cache/retry behavior.
# pyright: reportPrivateUsage=false
# pylint: disable=protected-access,redefined-outer-name,unused-argument

from __future__ import annotations

from urllib.parse import parse_qs

import pytest

from plynth.base.request import Request
from plynth.base.response import Response
from plynth.base.transport import AsyncTransport, SyncTransport
from tests.connectors.salesforce.auth.support import make_auth
from tests.connectors.salesforce.conftest import (
    DUMMY_ACCESS_TOKEN,
    DUMMY_CLIENT_ID,
    DUMMY_CLIENT_SECRET,
    DUMMY_INSTANCE_URL,
    FakeAsyncSalesforceTokenTransport,
    FakeSalesforceTokenTransport,
    render_json_bytes,
)


class TestSalesforceClientCredentialsAuthMiddleware:
    """Exercise sync client-credentials auth and instance_url caching behavior."""

    def test_instance_url_is_extracted_from_token_response(self) -> None:
        auth = make_auth()
        assert auth.instance_url == DUMMY_INSTANCE_URL

    def test_instance_url_triggers_token_fetch(self) -> None:
        transport = FakeSalesforceTokenTransport()
        auth = make_auth(transport)
        _ = auth.instance_url
        assert transport.calls == 1

    def test_instance_url_is_cached_alongside_token(self) -> None:
        transport = FakeSalesforceTokenTransport()
        auth = make_auth(transport)
        _ = auth.instance_url
        _ = auth.instance_url
        assert transport.calls == 1

    def test_access_token_and_instance_url_fetched_in_single_request(self) -> None:
        transport = FakeSalesforceTokenTransport()
        auth = make_auth(transport)
        headers = auth._get_token_header()
        assert headers == {"Authorization": f"Bearer {DUMMY_ACCESS_TOKEN}"}
        assert auth.instance_url == DUMMY_INSTANCE_URL
        assert transport.calls == 1

    def test_invalidate_clears_instance_url_cache(self) -> None:
        transport = FakeSalesforceTokenTransport()
        auth = make_auth(transport)
        _ = auth.instance_url
        auth._invalidate()
        _ = auth.instance_url
        assert transport.calls == 2

    def test_instance_url_updated_after_invalidate(self) -> None:
        new_instance_url = "https://neworg.my.salesforce.com"

        class _RotatingTransport(SyncTransport):
            calls: int = 0

            def send(self, request: Request) -> Response:
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
        auth = make_auth(transport)
        assert auth.instance_url == DUMMY_INSTANCE_URL
        auth._invalidate()
        assert auth.instance_url == new_instance_url

    def test_missing_instance_url_raises_runtime_error(self) -> None:
        transport = FakeSalesforceTokenTransport(include_instance_url=False)
        auth = make_auth(transport)
        with pytest.raises(RuntimeError, match="instance_url"):
            _ = auth.instance_url

    def test_empty_instance_url_raises_runtime_error(self) -> None:
        transport = FakeSalesforceTokenTransport(instance_url="")
        auth = make_auth(transport)
        with pytest.raises(RuntimeError, match="instance_url"):
            _ = auth.instance_url

    def test_authenticate_also_caches_instance_url(self) -> None:
        transport = FakeSalesforceTokenTransport()
        auth = make_auth(transport)
        auth._get_token_header()
        _ = auth.instance_url
        assert transport.calls == 1

    def test_error_response_raises_runtime_error(self) -> None:
        transport = FakeSalesforceTokenTransport(status=401)
        auth = make_auth(transport)
        with pytest.raises(RuntimeError, match="401"):
            _ = auth.instance_url

    def test_client_credentials_flow_sends_expected_form_fields(self) -> None:
        transport = FakeSalesforceTokenTransport()
        auth = make_auth(transport)
        _ = auth.instance_url
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["grant_type"] == ["client_credentials"]
        assert params["client_id"] == [DUMMY_CLIENT_ID]
        assert params["client_secret"] == [DUMMY_CLIENT_SECRET]


class TestAsyncSalesforceClientCredentialsAuthMiddleware:
    """Exercise async client-credentials auth and instance_url caching behavior."""

    async def test_get_instance_url_returns_instance_url(self) -> None:
        auth = make_auth(async_mode=True)
        assert await auth.get_instance_url() == DUMMY_INSTANCE_URL

    async def test_get_instance_url_triggers_token_fetch(self) -> None:
        transport = FakeAsyncSalesforceTokenTransport()
        auth = make_auth(transport, async_mode=True)
        await auth.get_instance_url()
        assert transport.calls == 1

    async def test_get_instance_url_is_cached_alongside_token(self) -> None:
        transport = FakeAsyncSalesforceTokenTransport()
        auth = make_auth(transport, async_mode=True)
        await auth.get_instance_url()
        await auth.get_instance_url()
        assert transport.calls == 1

    async def test_token_header_and_instance_url_fetched_in_single_request(
        self,
    ) -> None:
        transport = FakeAsyncSalesforceTokenTransport()
        auth = make_auth(transport, async_mode=True)
        headers = await auth._get_token_header()
        assert headers == {"Authorization": f"Bearer {DUMMY_ACCESS_TOKEN}"}
        assert await auth.get_instance_url() == DUMMY_INSTANCE_URL
        assert transport.calls == 1

    async def test_invalidate_clears_instance_url_cache(self) -> None:
        transport = FakeAsyncSalesforceTokenTransport()
        auth = make_auth(transport, async_mode=True)
        await auth.get_instance_url()
        auth._invalidate()
        await auth.get_instance_url()
        assert transport.calls == 2

    async def test_instance_url_updated_after_invalidate(self) -> None:
        new_instance_url = "https://neworg.my.salesforce.com"

        class _RotatingAsyncTransport(AsyncTransport):
            calls: int = 0

            async def send(self, request: Request) -> Response:
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
        auth = make_auth(transport, async_mode=True)
        assert await auth.get_instance_url() == DUMMY_INSTANCE_URL
        auth._invalidate()
        assert await auth.get_instance_url() == new_instance_url

    async def test_missing_instance_url_raises_runtime_error(self) -> None:
        transport = FakeAsyncSalesforceTokenTransport(include_instance_url=False)
        auth = make_auth(transport, async_mode=True)
        with pytest.raises(RuntimeError, match="instance_url"):
            await auth.get_instance_url()

    async def test_empty_instance_url_raises_runtime_error(self) -> None:
        transport = FakeAsyncSalesforceTokenTransport(instance_url="")
        auth = make_auth(transport, async_mode=True)
        with pytest.raises(RuntimeError, match="instance_url"):
            await auth.get_instance_url()

    async def test_authenticate_also_caches_instance_url(self) -> None:
        transport = FakeAsyncSalesforceTokenTransport()
        auth = make_auth(transport, async_mode=True)
        await auth._get_token_header()
        await auth.get_instance_url()
        assert transport.calls == 1

    async def test_error_response_raises_runtime_error(self) -> None:
        transport = FakeAsyncSalesforceTokenTransport(status=401)
        auth = make_auth(transport, async_mode=True)
        with pytest.raises(RuntimeError, match="401"):
            await auth.get_instance_url()

    async def test_client_credentials_flow_sends_expected_form_fields(self) -> None:
        transport = FakeAsyncSalesforceTokenTransport()
        auth = make_auth(transport, async_mode=True)
        await auth.get_instance_url()
        assert transport.last_request is not None
        assert transport.last_request.content is not None
        params = parse_qs(transport.last_request.content.decode())
        assert params["grant_type"] == ["client_credentials"]
        assert params["client_id"] == [DUMMY_CLIENT_ID]
        assert params["client_secret"] == [DUMMY_CLIENT_SECRET]
