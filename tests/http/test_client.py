"""Tests for HTTPClient and AsyncHTTPClient."""

from __future__ import annotations

import pytest

from plynth.base.response import Response
from plynth.http.client import APIClient, AsyncAPIClient, AsyncHTTPClient, HTTPClient
from plynth.http.errors import (
    HttpStatusError,
    InternalServerError,
    NotFoundError,
    UnauthorizedError,
)
from tests.conftest import BASE_URL, MockAsyncTransport, MockSyncTransport


class TestHTTPClient:
    """Test suite for HTTPClient."""

    def test_get_sends_correct_method_and_url(
        self, http_client: HTTPClient, sync_transport: MockSyncTransport
    ) -> None:
        """Validate get sends correct method and url."""
        http_client.get("/items")
        req = sync_transport.send.call_args[0][0]
        assert req.method == "GET"
        assert req.url == f"{BASE_URL}/items"

    def test_post_sends_correct_method_and_content(self) -> None:
        """Validate post sends correct method and content."""
        transport = MockSyncTransport(201)
        client = HTTPClient(base_url=BASE_URL, transport=transport)
        client.post("/items", content=b'{"name": "x"}')
        req = transport.send.call_args[0][0]
        assert req.method == "POST"
        assert req.content == b'{"name": "x"}'

    def test_put_sends_correct_method(
        self, http_client: HTTPClient, sync_transport: MockSyncTransport
    ) -> None:
        """Validate put sends correct method."""
        http_client.put("/items/1", content=b'{"name": "y"}')
        req = sync_transport.send.call_args[0][0]
        assert req.method == "PUT"

    def test_patch_sends_correct_method(
        self, http_client: HTTPClient, sync_transport: MockSyncTransport
    ) -> None:
        """Validate patch sends correct method."""
        http_client.patch("/items/1", content=b'{"name": "z"}')
        req = sync_transport.send.call_args[0][0]
        assert req.method == "PATCH"

    def test_delete_sends_correct_method(self) -> None:
        """Validate delete sends correct method."""
        transport = MockSyncTransport(204)
        client = HTTPClient(base_url=BASE_URL, transport=transport)
        client.delete("/items/1")
        req = transport.send.call_args[0][0]
        assert req.method == "DELETE"

    def test_base_url_trailing_slash_stripped(
        self, sync_transport: MockSyncTransport
    ) -> None:
        """Validate base url trailing slash stripped."""
        client = HTTPClient(base_url=f"{BASE_URL}/", transport=sync_transport)
        client.get("/items")
        req = sync_transport.send.call_args[0][0]
        assert req.url == f"{BASE_URL}/items"

    def test_path_leading_slash_normalised(
        self, http_client: HTTPClient, sync_transport: MockSyncTransport
    ) -> None:
        """Validate path leading slash normalised."""
        http_client.get("items")
        req = sync_transport.send.call_args[0][0]
        assert req.url == f"{BASE_URL}/items"

    def test_default_headers_merged(self, sync_transport: MockSyncTransport) -> None:
        """Validate default headers merged."""
        client = HTTPClient(
            base_url=BASE_URL,
            transport=sync_transport,
            headers={"User-Agent": "test/1.0"},
        )
        client.get("/items")
        req = sync_transport.send.call_args[0][0]
        assert req.headers["User-Agent"] == "test/1.0"

    def test_per_call_headers_override_defaults(
        self, sync_transport: MockSyncTransport
    ) -> None:
        """Validate per call headers override defaults."""
        client = HTTPClient(
            base_url=BASE_URL,
            transport=sync_transport,
            headers={"X-Version": "1"},
        )
        client.get("/items", headers={"X-Version": "2"})
        req = sync_transport.send.call_args[0][0]
        assert req.headers["X-Version"] == "2"

    def test_params_forwarded(
        self, http_client: HTTPClient, sync_transport: MockSyncTransport
    ) -> None:
        """Validate params forwarded."""
        http_client.get("/items", params={"page": 2})
        req = sync_transport.send.call_args[0][0]
        assert req.params == {"page": 2}

    def test_returns_response(self) -> None:
        """Validate returns response."""
        transport = MockSyncTransport(200, b"ok")
        client = HTTPClient(base_url=BASE_URL, transport=transport)
        resp = client.get("/items")
        assert isinstance(resp, Response)
        assert resp.status_code == 200
        assert resp.content == b"ok"

    def test_non_200_returned_without_raising(self) -> None:
        """Validate non 200 returned without raising."""
        transport = MockSyncTransport(404)
        client = HTTPClient(base_url=BASE_URL, transport=transport)
        resp = client.get("/items/99")
        assert resp.status_code == 404


class TestAsyncHTTPClient:
    """Test suite for AsyncHTTPClient."""

    async def test_get_sends_correct_method_and_url(
        self, async_http_client: AsyncHTTPClient, async_transport: MockAsyncTransport
    ) -> None:
        """Validate get sends correct method and url."""
        await async_http_client.get("/items")
        req = async_transport.send.call_args[0][0]
        assert req.method == "GET"
        assert req.url == f"{BASE_URL}/items"

    async def test_post_sends_content(self) -> None:
        """Validate post sends content."""
        transport = MockAsyncTransport(201)
        client = AsyncHTTPClient(base_url=BASE_URL, transport=transport)
        await client.post("/items", content=b'{"x": 1}')
        req = transport.send.call_args[0][0]
        assert req.method == "POST"
        assert req.content == b'{"x": 1}'

    async def test_put_sends_correct_method(
        self, async_http_client: AsyncHTTPClient, async_transport: MockAsyncTransport
    ) -> None:
        """Validate put sends correct method."""
        await async_http_client.put("/items/1", content=b"{}")
        req = async_transport.send.call_args[0][0]
        assert req.method == "PUT"

    async def test_patch_sends_correct_method(
        self, async_http_client: AsyncHTTPClient, async_transport: MockAsyncTransport
    ) -> None:
        """Validate patch sends correct method."""
        await async_http_client.patch("/items/1", content=b"{}")
        req = async_transport.send.call_args[0][0]
        assert req.method == "PATCH"

    async def test_delete_sends_correct_method(self) -> None:
        """Validate delete sends correct method."""
        transport = MockAsyncTransport(204)
        client = AsyncHTTPClient(base_url=BASE_URL, transport=transport)
        await client.delete("/items/1")
        req = transport.send.call_args[0][0]
        assert req.method == "DELETE"

    async def test_default_headers_merged(
        self, async_transport: MockAsyncTransport
    ) -> None:
        """Validate default headers merged."""
        client = AsyncHTTPClient(
            base_url=BASE_URL,
            transport=async_transport,
            headers={"User-Agent": "async-test/1.0"},
        )
        await client.get("/items")
        req = async_transport.send.call_args[0][0]
        assert req.headers["User-Agent"] == "async-test/1.0"

    async def test_returns_response(self) -> None:
        """Validate returns response."""
        transport = MockAsyncTransport(200, b"ok")
        client = AsyncHTTPClient(base_url=BASE_URL, transport=transport)
        resp = await client.get("/items")
        assert isinstance(resp, Response)
        assert resp.status_code == 200

    async def test_non_200_returned_without_raising(self) -> None:
        """Validate non 200 returned without raising."""
        transport = MockAsyncTransport(503)
        client = AsyncHTTPClient(base_url=BASE_URL, transport=transport)
        resp = await client.get("/items")
        assert resp.status_code == 503


class TestAPIClient:
    """Test suite for APIClient."""

    def test_json_content_type_sent_by_default(
        self, api_client: APIClient, sync_transport: MockSyncTransport
    ) -> None:
        """Validate json content type sent by default."""
        api_client.get("/items")
        req = sync_transport.send.call_args[0][0]
        assert req.headers["Content-Type"] == "application/json"
        assert req.headers["Accept"] == "application/json"

    def test_custom_headers_merged_with_json_defaults(
        self, sync_transport: MockSyncTransport
    ) -> None:
        """Validate custom headers merged with json defaults."""
        client = APIClient(
            base_url=BASE_URL,
            transport=sync_transport,
            headers={"Authorization": "Bearer token"},
        )
        client.get("/items")
        req = sync_transport.send.call_args[0][0]
        assert req.headers["Authorization"] == "Bearer token"
        assert req.headers["Accept"] == "application/json"

    def test_successful_response_returned(self) -> None:
        """Validate successful response returned."""
        transport = MockSyncTransport(200, b'{"ok": true}')
        client = APIClient(base_url=BASE_URL, transport=transport)
        resp = client.get("/items")
        assert resp.status_code == 200
        assert resp.content == b'{"ok": true}'

    def test_404_raises_not_found_error(self) -> None:
        """Validate 404 raises not found error."""
        transport = MockSyncTransport(404)
        client = APIClient(base_url=BASE_URL, transport=transport)
        with pytest.raises(NotFoundError):
            client.get("/items/99")

    def test_401_raises_unauthorized_error(self) -> None:
        """Validate 401 raises unauthorized error."""
        transport = MockSyncTransport(401)
        client = APIClient(base_url=BASE_URL, transport=transport)
        with pytest.raises(UnauthorizedError):
            client.get("/protected")

    def test_500_raises_internal_server_error(self) -> None:
        """Validate 500 raises internal server error."""
        transport = MockSyncTransport(500)
        client = APIClient(base_url=BASE_URL, transport=transport)
        with pytest.raises(InternalServerError):
            client.get("/items")

    def test_error_is_http_status_error(self) -> None:
        """All raised errors are catchable as HttpStatusError."""
        transport = MockSyncTransport(403)
        client = APIClient(base_url=BASE_URL, transport=transport)
        with pytest.raises(HttpStatusError) as exc_info:
            client.get("/admin")
        assert exc_info.value.status_code == 403

    def test_error_carries_method_and_url(self) -> None:
        """Validate error carries method and url."""
        transport = MockSyncTransport(404)
        client = APIClient(base_url=BASE_URL, transport=transport)
        with pytest.raises(HttpStatusError) as exc_info:
            client.get("/items/1")
        err = exc_info.value
        assert err.method == "GET"
        assert "items/1" in err.url

    def test_error_carries_raw_response(self) -> None:
        """Validate error carries raw response."""
        transport = MockSyncTransport(404, b'{"detail": "not found"}')
        client = APIClient(base_url=BASE_URL, transport=transport)
        with pytest.raises(HttpStatusError) as exc_info:
            client.get("/items/1")
        assert exc_info.value._response is not None
        assert exc_info.value._response.status_code == 404
        assert exc_info.value._response.content == b'{"detail": "not found"}'

    def test_post_with_content(self) -> None:
        """Validate post with content."""
        transport = MockSyncTransport(201)
        client = APIClient(base_url=BASE_URL, transport=transport)
        resp = client.post("/items", content=b'{"name": "widget"}')
        assert resp.status_code == 201

    def test_delete_success(self) -> None:
        """Validate delete success."""
        transport = MockSyncTransport(204)
        client = APIClient(base_url=BASE_URL, transport=transport)
        resp = client.delete("/items/1")
        assert resp.status_code == 204

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 409, 422, 500, 503])
    def test_all_error_codes_raise_http_status_error(self, status_code: int) -> None:
        """Validate all error codes raise http status error."""
        transport = MockSyncTransport(status_code)
        client = APIClient(base_url=BASE_URL, transport=transport)
        with pytest.raises(HttpStatusError) as exc_info:
            client.get("/items")
        assert exc_info.value.status_code == status_code


class TestAsyncAPIClient:
    """Test suite for AsyncAPIClient."""

    async def test_json_content_type_sent_by_default(
        self, async_api_client: AsyncAPIClient, async_transport: MockAsyncTransport
    ) -> None:
        """Validate json content type sent by default."""
        await async_api_client.get("/items")
        req = async_transport.send.call_args[0][0]
        assert req.headers["Content-Type"] == "application/json"
        assert req.headers["Accept"] == "application/json"

    async def test_successful_response_returned(self) -> None:
        """Validate successful response returned."""
        transport = MockAsyncTransport(200, b'{"ok": true}')
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        resp = await client.get("/items")
        assert resp.status_code == 200

    async def test_404_raises_not_found_error(self) -> None:
        """Validate 404 raises not found error."""
        transport = MockAsyncTransport(404)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        with pytest.raises(NotFoundError):
            await client.get("/items/99")

    async def test_500_raises_internal_server_error(self) -> None:
        """Validate 500 raises internal server error."""
        transport = MockAsyncTransport(500)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        with pytest.raises(InternalServerError):
            await client.get("/items")

    async def test_error_carries_method_and_url(self) -> None:
        """Validate error carries method and url."""
        transport = MockAsyncTransport(404)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        with pytest.raises(HttpStatusError) as exc_info:
            await client.post("/items", content=b"{}")
        err = exc_info.value
        assert err.method == "POST"
        assert "items" in err.url

    async def test_error_carries_raw_response(self) -> None:
        """Validate error carries raw response."""
        transport = MockAsyncTransport(500, b'{"error": "boom"}')
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        with pytest.raises(HttpStatusError) as exc_info:
            await client.get("/items")
        assert exc_info.value._response is not None
        assert exc_info.value._response.status_code == 500
        assert exc_info.value._response.content == b'{"error": "boom"}'

    async def test_post_with_content(self) -> None:
        """Validate post with content."""
        transport = MockAsyncTransport(201)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        resp = await client.post("/items", content=b'{"name": "widget"}')
        assert resp.status_code == 201

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422, 500, 503])
    async def test_all_error_codes_raise_http_status_error(
        self, status_code: int
    ) -> None:
        """Validate all error codes raise http status error."""
        transport = MockAsyncTransport(status_code)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        with pytest.raises(HttpStatusError) as exc_info:
            await client.get("/items")
        assert exc_info.value.status_code == status_code
