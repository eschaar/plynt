"""Smoke-test installed distributions without importing repository fixtures

CI runs this file with ``--noconftest --import-mode=importlib -c /dev/null``.
``PLYNTH_WHEEL_PROFILE`` selects a clean installation profile; when absent,
the normal full suite exercises every implemented optional integration.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from importlib import metadata, resources
from importlib.util import find_spec
from pathlib import Path

import pytest

_PROFILE: str = os.environ.get("PLYNTH_WHEEL_PROFILE", "full")
_MODULES: dict[str, tuple[str, ...]] = {
    "core": ("plynth.base", "plynth.http", "plynth.middleware", "plynth.cache"),
    "httpx": ("plynth.http.transport", "plynth.connectors.llm"),
    "grpc": ("plynth.grpc",),
    "cdc": ("plynth.connectors.salesforce.cdc",),
    "django": ("plynth.adapters.django",),
    "drf": ("plynth.adapters.django.drf",),
    "fastapi": ("plynth.adapters.fastapi",),
}
_SELECTED = (
    tuple(_MODULES)
    if _PROFILE == "full"
    else ("core", _PROFILE)
    if _PROFILE != "core"
    else ("core",)
)


class TestInstalledDistribution:
    """Verify public imports, packaged resources, and real decoder usability"""

    @pytest.mark.parametrize("profile", _SELECTED)
    def test_public_modules_import(self, profile: str) -> None:
        for name in _MODULES[profile]:
            module = importlib.import_module(name)
            if "PLYNTH_WHEEL_PROFILE" in os.environ:
                assert module.__file__ is not None
                assert (
                    Path(module.__file__)
                    .resolve()
                    .is_relative_to(Path(sys.prefix).resolve())
                ), f"{name} was imported from the checkout rather than the wheel"

    def test_core_models_work(self) -> None:
        from plynth.base import Request, Response

        request = Request(method="GET", url="https://example.invalid/items")
        response = Response(status_code=200, content=b'{"ok":true}')

        assert request.method == "GET"
        assert response.content == b'{"ok":true}'

    def test_declared_extras_are_complete(self) -> None:
        package = metadata.metadata("plynth")
        extras = set(package.get_all("Provides-Extra") or [])

        assert {"httpx", "grpc", "salesforce", "django", "drf", "fastapi"} <= extras
        requirements = metadata.requires("plynth") or []
        assert any(
            requirement.startswith("fastavro")
            and 'extra == "salesforce"' in requirement
            for requirement in requirements
        )

    def test_sync_http_client_uses_caller_supplied_transport(self) -> None:
        from plynth.base import Request, Response, SyncTransport
        from plynth.http import HTTPClient

        class CustomTransport(SyncTransport):
            def send(self, request: Request) -> Response:
                return Response(status_code=200, content=request.url.encode())

        client = HTTPClient("https://example.invalid", CustomTransport())
        assert client.get("/items").content == b"https://example.invalid/items"

    def test_async_http_client_uses_caller_supplied_transport(self) -> None:
        from plynth.base import AsyncTransport, Request, Response
        from plynth.http import AsyncHTTPClient

        class CustomTransport(AsyncTransport):
            async def send(self, request: Request) -> Response:
                return Response(status_code=200, content=request.url.encode())

        client = AsyncHTTPClient("https://example.invalid", CustomTransport())
        response = asyncio.run(client.get("/items"))
        assert response.content == b"https://example.invalid/items"

    def test_isolated_dependencies_match_profile(self) -> None:
        if "PLYNTH_WHEEL_PROFILE" in os.environ:
            assert find_spec("grpc_tools") is None
            assert find_spec("setuptools") is None
        if _PROFILE == "core":
            for module in (
                "grpc",
                "fastavro",
                "fastapi",
                "django",
                "rest_framework",
                "httpx2",
            ):
                assert find_spec(module) is None
        else:
            assert _PROFILE in _MODULES or _PROFILE == "full"

    def test_http_backend_construction_boundary(self) -> None:
        from plynth.http import HttpxAsyncTransport, HttpxSyncTransport
        from plynth.http.settings import HTTPSettings

        if find_spec("httpx2") is None:
            for transport_type in (HttpxSyncTransport, HttpxAsyncTransport):
                with pytest.raises(ImportError, match=r"plynth\[httpx\]"):
                    transport_type()
                with pytest.raises(ImportError, match=r"plynth\[httpx\]"):
                    transport_type.from_settings(HTTPSettings())
        else:
            with HttpxSyncTransport.from_settings(HTTPSettings()) as transport:
                assert isinstance(transport, HttpxSyncTransport)
            asyncio.run(self._construct_and_close_async_transport())

    @pytest.mark.parametrize("profile", ("cdc",) if _PROFILE in {"cdc", "full"} else ())
    def test_cdc_messages_and_real_avro_decoder_work(self, profile: str) -> None:
        from plynth.connectors.salesforce.cdc import AvroPayloadDecoder
        from plynth.connectors.salesforce.cdc._proto import pubsub_api_pb2

        request = pubsub_api_pb2.FetchRequest(
            topic_name="/data/AccountChangeEvent", num_requested=1
        )
        restored = pubsub_api_pb2.FetchRequest.FromString(request.SerializeToString())
        assert restored.topic_name == request.topic_name
        schema = (
            '{"type":"record","name":"Account",'
            '"fields":[{"name":"Name","type":"string"}]}'
        )
        assert AvroPayloadDecoder().decode(schema, b"\x06Ada") == {"Name": "Ada"}
        proto = resources.files("plynth.connectors.salesforce.cdc._proto")
        assert "service PubSub" in proto.joinpath("pubsub_api.proto").read_text()
        assert proto.joinpath("SOURCE.md").is_file()

        asyncio.run(self._build_adapter())

    @staticmethod
    async def _construct_and_close_async_transport() -> None:
        from plynth.http import HttpxAsyncTransport
        from plynth.http.settings import HTTPSettings

        async with HttpxAsyncTransport.from_settings(HTTPSettings()) as transport:
            assert isinstance(transport, HttpxAsyncTransport)

    @staticmethod
    async def _build_adapter() -> None:
        import grpc

        from plynth.connectors.salesforce.cdc import create_vendored_pubsub_adapter

        channel = grpc.aio.insecure_channel("127.0.0.1:1")
        try:
            assert create_vendored_pubsub_adapter(channel) is not None
        finally:
            await channel.close()
