"""Tests for HTTPService, AsyncHTTPService, Renderer, and JSONRenderer."""

from __future__ import annotations

import json
from typing import Any

import pytest

from plynt.base.response import Response
from plynt.http.client import APIClient, AsyncAPIClient, AsyncHTTPClient, HTTPClient
from plynt.http.renderer import ExtendedJSONRenderer, JSONRenderer, Renderer
from plynt.http.service import (
    APIService,
    AsyncAPIService,
    AsyncHTTPService,
    HTTPService,
)
from tests.conftest import BASE_URL, MockAsyncTransport, MockSyncTransport


class TestHTTPService:
    """Test suite for HTTPService."""

    @pytest.fixture
    def service(self, http_client: HTTPClient) -> HTTPService:
        """Return service."""
        return HTTPService(client=http_client)

    def test_client_is_stored(
        self, service: HTTPService, http_client: HTTPClient
    ) -> None:
        """Validate client is stored."""
        assert service._client is http_client

    def test_renderer_defaults_to_none(self, service: HTTPService) -> None:
        """Validate renderer defaults to none."""
        assert service._renderer is None

    def test_renderer_is_stored_when_provided(self, http_client: HTTPClient) -> None:
        """Validate renderer is stored when provided."""
        renderer = JSONRenderer()
        service = HTTPService(client=http_client, renderer=renderer)
        assert service._renderer is renderer

    def test_subclass_can_use_client(self) -> None:
        """Validate subclass can use client."""
        transport = MockSyncTransport(200, b"ok")
        client = HTTPClient(base_url=BASE_URL, transport=transport)

        class ConcreteService(HTTPService):
            """Represent ConcreteService."""

            def fetch(self) -> Response:
                """Return fetch."""
                return self._client.get("/items")

        svc = ConcreteService(client=client)
        resp = svc.fetch()
        assert resp.status_code == 200
        assert resp.content == b"ok"

    def test_subclass_can_use_renderer(self) -> None:
        """Validate subclass can use renderer."""
        transport = MockSyncTransport(201, b"created")
        client = HTTPClient(base_url=BASE_URL, transport=transport)
        renderer = JSONRenderer()

        class ConcreteService(HTTPService):
            """Represent ConcreteService."""

            def create(self, data: dict[str, object]) -> Response:
                """Return create."""
                body = self._renderer.render(data)  # type: ignore[union-attr]
                return self._client.post("/items", content=body)

        svc = ConcreteService(client=client, renderer=renderer)
        resp = svc.create({"key": "val"})
        sent_content = transport.send.call_args[0][0].content
        assert json.loads(sent_content) == {"key": "val"}
        assert resp.status_code == 201


class TestAsyncHTTPService:
    """Test suite for AsyncHTTPService."""

    @pytest.fixture
    def service(self, async_http_client: AsyncHTTPClient) -> AsyncHTTPService:
        """Return service."""
        return AsyncHTTPService(client=async_http_client)

    def test_client_is_stored(
        self, service: AsyncHTTPService, async_http_client: AsyncHTTPClient
    ) -> None:
        """Validate client is stored."""
        assert service._client is async_http_client

    def test_renderer_defaults_to_none(self, service: AsyncHTTPService) -> None:
        """Validate renderer defaults to none."""
        assert service._renderer is None

    def test_renderer_is_stored_when_provided(
        self, async_http_client: AsyncHTTPClient
    ) -> None:
        """Validate renderer is stored when provided."""
        renderer = JSONRenderer()
        service = AsyncHTTPService(client=async_http_client, renderer=renderer)
        assert service._renderer is renderer

    async def test_subclass_can_use_client(self) -> None:
        """Validate subclass can use client."""
        transport = MockAsyncTransport(200, b"ok")
        client = AsyncHTTPClient(base_url=BASE_URL, transport=transport)

        class ConcreteService(AsyncHTTPService):
            """Represent ConcreteService."""

            async def fetch(self) -> Response:
                """Return fetch."""
                return await self._client.get("/items")

        svc = ConcreteService(client=client)
        resp = await svc.fetch()
        assert resp.status_code == 200
        assert resp.content == b"ok"

    async def test_subclass_can_use_renderer(self) -> None:
        """Validate subclass can use renderer."""
        transport = MockAsyncTransport(201, b"created")
        client = AsyncHTTPClient(base_url=BASE_URL, transport=transport)
        renderer = JSONRenderer()

        class ConcreteService(AsyncHTTPService):
            """Represent ConcreteService."""

            async def create(self, data: dict[str, object]) -> Response:
                """Return create."""
                body = self._renderer.render(data)  # type: ignore[union-attr]
                return await self._client.post("/items", content=body)

        svc = ConcreteService(client=client, renderer=renderer)
        resp = await svc.create({"key": "val"})
        sent_content = transport.send.call_args[0][0].content
        assert json.loads(sent_content) == {"key": "val"}
        assert resp.status_code == 201


class TestJSONRenderer:
    """Test suite for JSONRenderer."""

    @pytest.fixture
    def renderer(self) -> JSONRenderer:
        """Return renderer."""
        return JSONRenderer()

    def test_renders_dict_to_json_bytes(self, renderer: JSONRenderer) -> None:
        """Validate renders dict to json bytes."""
        result = renderer.render({"key": "value", "num": 42})
        assert json.loads(result) == {"key": "value", "num": 42}

    def test_renders_list_to_json_bytes(self, renderer: JSONRenderer) -> None:
        """Validate renders list to json bytes."""
        result = renderer.render([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_renders_string_to_json_bytes(self, renderer: JSONRenderer) -> None:
        """Validate renders string to json bytes."""
        result = renderer.render("hello")
        assert json.loads(result) == "hello"

    def test_renders_none_to_json_bytes(self, renderer: JSONRenderer) -> None:
        """Validate renders none to json bytes."""
        result = renderer.render(None)
        assert result == b"null"

    def test_output_is_bytes(self, renderer: JSONRenderer) -> None:
        """Validate output is bytes."""
        result = renderer.render({"x": 1})
        assert isinstance(result, bytes)

    def test_output_is_utf8_encoded(self, renderer: JSONRenderer) -> None:
        """Validate output is utf8 encoded."""
        result = renderer.render({"emoji": "\u2603"})
        assert result.decode("utf-8")


class TestExtendedJSONRenderer:
    """Test suite for ExtendedJSONRenderer."""

    @pytest.fixture
    def renderer(self) -> ExtendedJSONRenderer:
        """Return renderer."""
        return ExtendedJSONRenderer()

    def test_renders_simple_dict(self, renderer: ExtendedJSONRenderer) -> None:
        """Validate renders simple dict."""
        result = renderer.render({"key": "value"})
        assert json.loads(result) == {"key": "value"}

    def test_output_is_bytes(self, renderer: ExtendedJSONRenderer) -> None:
        """Validate output is bytes."""
        assert isinstance(renderer.render({"x": 1}), bytes)

    def test_renders_datetime(self, renderer: ExtendedJSONRenderer) -> None:
        """Validate renders datetime."""
        import datetime

        result = renderer.render({"ts": datetime.datetime(2026, 3, 22, 14, 0, 0)})
        assert json.loads(result) == {"ts": "2026-03-22T14:00:00"}

    def test_renders_date(self, renderer: ExtendedJSONRenderer) -> None:
        """Validate renders date."""
        import datetime

        result = renderer.render({"d": datetime.date(2026, 3, 22)})
        assert json.loads(result) == {"d": "2026-03-22"}

    def test_renders_time(self, renderer: ExtendedJSONRenderer) -> None:
        """Validate renders time."""
        import datetime

        result = renderer.render({"t": datetime.time(14, 0, 0)})
        assert json.loads(result) == {"t": "14:00:00"}

    def test_renders_decimal(self, renderer: ExtendedJSONRenderer) -> None:
        """Validate renders decimal."""
        import decimal

        result = renderer.render({"amount": decimal.Decimal("9999.99")})
        assert json.loads(result) == {"amount": "9999.99"}

    def test_renders_uuid(self, renderer: ExtendedJSONRenderer) -> None:
        """Validate renders uuid."""
        import uuid

        uid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = renderer.render({"id": uid})
        assert json.loads(result) == {"id": "12345678-1234-5678-1234-567812345678"}

    def test_raises_for_unserializable_type(
        self, renderer: ExtendedJSONRenderer
    ) -> None:
        """Validate raises for unserializable type."""
        with pytest.raises(TypeError):
            renderer.render({"value": object()})


class TestRendererProtocol:
    """Test suite for RendererProtocol."""

    def test_json_renderer_satisfies_protocol(self) -> None:
        """Validate json renderer satisfies protocol."""
        assert isinstance(JSONRenderer(), Renderer)

    def test_extended_json_renderer_satisfies_protocol(self) -> None:
        """Validate extended json renderer satisfies protocol."""
        assert isinstance(ExtendedJSONRenderer(), Renderer)

    def test_custom_renderer_satisfies_protocol(self) -> None:
        """Validate custom renderer satisfies protocol."""

        class FormRenderer:
            """Represent FormRenderer."""

            def render(self, data: dict[str, object]) -> bytes:
                """Return render."""
                return "&".join(f"{k}={v}" for k, v in data.items()).encode()

        assert isinstance(FormRenderer(), Renderer)

    def test_object_without_render_does_not_satisfy_protocol(self) -> None:
        """Validate object without render does not satisfy protocol."""

        class NotARenderer:
            """Represent NotARenderer."""

            pass

        assert not isinstance(NotARenderer(), Renderer)


class TestAPIService:
    """Test suite for APIService."""

    @pytest.fixture
    def service(self, api_client: APIClient) -> APIService:
        """Return service."""
        return APIService(client=api_client)

    def test_client_is_stored(self, service: APIService, api_client: APIClient) -> None:
        """Validate client is stored."""
        assert service._client is api_client

    def test_renderer_defaults_to_json_renderer(self, service: APIService) -> None:
        """Validate renderer defaults to json renderer."""
        assert isinstance(service._renderer, JSONRenderer)

    def test_custom_renderer_is_stored(self, api_client: APIClient) -> None:
        """Validate custom renderer is stored."""

        class XmlRenderer:
            """Represent XmlRenderer."""

            def render(self, data: object) -> bytes:
                """Return render."""
                return b"<xml/>"

        svc = APIService(client=api_client, renderer=XmlRenderer())
        assert isinstance(svc._renderer, XmlRenderer)

    def test_satisfies_renderer_protocol(self, service: APIService) -> None:
        """Validate satisfies renderer protocol."""
        assert isinstance(service._renderer, Renderer)

    def test_subclass_can_use_client(self) -> None:
        """Validate subclass can use client."""
        transport = MockSyncTransport(200, b'{"id": 1}')
        client = APIClient(base_url=BASE_URL, transport=transport)

        class ProductService(APIService):
            """Represent ProductService."""

            def get_product(self) -> Response:
                """Return get product."""
                return self._client.get("/products/1")

        svc = ProductService(client=client)
        resp = svc.get_product()
        assert resp.status_code == 200
        assert resp.content == b'{"id": 1}'

    def test_subclass_can_use_renderer(self) -> None:
        """Validate subclass can use renderer."""
        transport = MockSyncTransport(201, b'{"id": 2}')
        client = APIClient(base_url=BASE_URL, transport=transport)

        class ProductService(APIService):
            """Represent ProductService."""

            def create_product(self, data: dict[str, Any]) -> Response:
                """Return create product."""
                return self._client.post(
                    "/products",
                    content=self._renderer.render(data),
                )

        svc = ProductService(client=client)
        svc.create_product({"name": "widget"})
        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content) == {"name": "widget"}

    def test_subclass_can_post(self) -> None:
        """Validate subclass can post."""
        transport = MockSyncTransport(201, b'{"id": 2}')
        client = APIClient(base_url=BASE_URL, transport=transport)

        class ProductService(APIService):
            """Represent ProductService."""

            def create_product(self, body: bytes) -> Response:
                """Return create product."""
                return self._client.post("/products", content=body)

        svc = ProductService(client=client)
        resp = svc.create_product(b'{"name": "widget"}')
        assert resp.status_code == 201


class TestAsyncAPIService:
    """Test suite for AsyncAPIService."""

    @pytest.fixture
    def service(self, async_api_client: AsyncAPIClient) -> AsyncAPIService:
        """Return service."""
        return AsyncAPIService(client=async_api_client)

    def test_client_is_stored(
        self, service: AsyncAPIService, async_api_client: AsyncAPIClient
    ) -> None:
        """Validate client is stored."""
        assert service._client is async_api_client

    def test_renderer_defaults_to_json_renderer(self, service: AsyncAPIService) -> None:
        """Validate renderer defaults to json renderer."""
        assert isinstance(service._renderer, JSONRenderer)

    async def test_subclass_can_use_client(self) -> None:
        """Validate subclass can use client."""
        transport = MockAsyncTransport(200, b'{"id": 1}')
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)

        class AsyncProductService(AsyncAPIService):
            """Represent AsyncProductService."""

            async def get_product(self) -> Response:
                """Return get product."""
                return await self._client.get("/products/1")

        svc = AsyncProductService(client=client)
        resp = await svc.get_product()
        assert resp.status_code == 200
        assert resp.content == b'{"id": 1}'

    async def test_subclass_can_post(self) -> None:
        """Validate subclass can post."""
        transport = MockAsyncTransport(201, b'{"id": 2}')
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)

        class AsyncProductService(AsyncAPIService):
            """Represent AsyncProductService."""

            async def create_product(self, body: bytes) -> Response:
                """Return create product."""
                return await self._client.post("/products", content=body)

        svc = AsyncProductService(client=client)
        resp = await svc.create_product(b'{"name": "widget"}')
        assert resp.status_code == 201
