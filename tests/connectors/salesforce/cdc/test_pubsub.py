"""Focused tests for Salesforce CDC Pub/Sub adapter primitives."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import grpc
import pytest

from plynt.connectors.salesforce.cdc._proto import pubsub_api_pb2
from plynt.connectors.salesforce.cdc.pubsub import (
    GrpcMethodPubSubAdapter,
    GrpcStubPubSubAdapter,
    create_vendored_pubsub_adapter,
)


class _FakeMethodClient:
    """Small method-based gRPC client double."""

    def __init__(self) -> None:
        """Initialize deterministic call recordings."""
        self.stream_calls: list[dict[str, Any]] = []
        self.unary_calls: list[dict[str, Any]] = []

    async def stream_stream(
        self,
        method: str,
        requests: AsyncIterator[dict[str, Any]],
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Capture stream call arguments and return one fake response."""
        captured_requests = [request async for request in requests]
        self.stream_calls.append(
            {
                "method": method,
                "requests": captured_requests,
                "metadata": metadata,
                "timeout": timeout,
            }
        )

        async def _stream() -> AsyncIterator[dict[str, Any]]:
            yield {"latest_replay_id": 7, "events": []}

        return _stream()

    async def unary_unary(
        self,
        method: str,
        request: dict[str, Any],
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, str]:
        """Capture unary call arguments and return schema JSON."""
        self.unary_calls.append(
            {
                "method": method,
                "request": request,
                "metadata": metadata,
                "timeout": timeout,
            }
        )
        return {"schema_json": '{"type": "record"}'}


@dataclass
class _FakePayload:
    """Generated-payload-like response stand-in."""

    schema_id: str
    payload: bytes
    topic_name: str
    replay_id: bytes


@dataclass
class _FakeConsumerEvent:
    """Generated-consumer-event-like response stand-in."""

    event: _FakePayload
    replay_id: bytes


@dataclass
class _FakeFetchResponse:
    """Generated-fetch-response-like stand-in."""

    latest_replay_id: bytes
    events: list[_FakeConsumerEvent]


@dataclass
class _FakeGetSchemaResponse:
    """Generated-get-schema-like stand-in."""

    schema_json: str


class _FakeStub:
    """Small generated-stub-like double."""

    def __init__(self) -> None:
        """Initialize deterministic call recordings."""
        self.subscribe_calls: list[dict[str, Any]] = []
        self.schema_calls: list[dict[str, Any]] = []

    def subscribe(
        self,
        requests: AsyncIterator[dict[str, Any]],
        *,
        metadata: tuple[tuple[str, str], ...] | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[_FakeFetchResponse]:
        """Capture call arguments and return one generated-like response."""

        async def _stream() -> AsyncIterator[_FakeFetchResponse]:
            captured_requests = [request async for request in requests]
            self.subscribe_calls.append(
                {
                    "requests": captured_requests,
                    "metadata": metadata,
                    "timeout": timeout,
                }
            )
            yield _FakeFetchResponse(
                latest_replay_id=(42).to_bytes(2, byteorder="big"),
                events=[
                    _FakeConsumerEvent(
                        event=_FakePayload(
                            schema_id="schema-1",
                            payload=b"abc",
                            topic_name="/data/AccountChangeEvent",
                            replay_id=(41).to_bytes(2, byteorder="big"),
                        ),
                        replay_id=(41).to_bytes(2, byteorder="big"),
                    )
                ],
            )

        return _stream()

    async def get_schema(
        self,
        request: dict[str, Any],
        *,
        metadata: tuple[tuple[str, str], ...] | None = None,
        timeout: float | None = None,
    ) -> _FakeGetSchemaResponse:
        """Capture call arguments and return a generated-like schema payload."""
        self.schema_calls.append(
            {
                "request": request,
                "metadata": metadata,
                "timeout": timeout,
            }
        )
        return _FakeGetSchemaResponse(schema_json='{"name": "Account"}')


_FakeStub.Subscribe = _FakeStub.subscribe  # type: ignore[attr-defined]
_FakeStub.GetSchema = _FakeStub.get_schema  # type: ignore[attr-defined]


class TestGrpcMethodPubSubAdapter:
    """Verify method-based Pub/Sub adapter contracts."""

    @pytest.mark.asyncio
    async def test_subscribe_and_get_schema_delegate_to_method_client(self) -> None:
        """Forward Subscribe/GetSchema calls through configured method names."""
        client = _FakeMethodClient()
        adapter = GrpcMethodPubSubAdapter(
            client,
            subscribe_method="/eventbus.v1.PubSub/Subscribe",
            schema_method="/eventbus.v1.PubSub/GetSchema",
        )

        async def _requests() -> AsyncIterator[dict[str, Any]]:
            yield {
                "topic_name": "/data/AccountChangeEvent",
                "replay_preset": "LATEST",
                "replay_id": None,
                "num_requested": 1,
            }

        stream = await adapter.subscribe(
            _requests(),
            metadata={"tenantid": "00Dxx"},
            timeout=5.0,
        )
        first = await anext(stream)
        schema_json = await adapter.get_schema_json(
            "schema-1",
            metadata={"tenantid": "00Dxx"},
            timeout=3.0,
        )

        assert first["latest_replay_id"] == 7
        assert schema_json == '{"type": "record"}'
        assert client.stream_calls[0]["method"] == "/eventbus.v1.PubSub/Subscribe"
        assert client.unary_calls[0]["method"] == "/eventbus.v1.PubSub/GetSchema"


class TestGrpcStubPubSubAdapter:
    """Verify generated-stub Pub/Sub adapter contracts."""

    @pytest.mark.parametrize(
        ("response", "expected"),
        [
            (
                {"latest_replay_id": 7, "events": []},
                {"latest_replay_id": 7, "events": []},
            ),
            (
                SimpleNamespace(
                    latest_replay_id=7,
                    events=[
                        {"replay_id": 6, "event": {"schema_id": "schema-1"}},
                        SimpleNamespace(event=None, replay_id=None),
                    ],
                ),
                {
                    "latest_replay_id": 7,
                    "events": [{"replay_id": 6, "event": {"schema_id": "schema-1"}}],
                },
            ),
            (
                SimpleNamespace(
                    latest_replay_id=b"",
                    events=[SimpleNamespace(event=None, replay_id=7)],
                ),
                {"latest_replay_id": 0, "events": [{"replay_id": 7}]},
            ),
        ],
    )
    async def test_normalizes_custom_stub_responses(
        self, response: Any, expected: dict[str, Any]
    ) -> None:
        async def responses(
            requests: AsyncIterator[dict[str, Any]], **kwargs: Any
        ) -> AsyncIterator[Any]:
            assert (await anext(requests))["topic_name"] == "/data/AccountChangeEvent"
            yield response

        adapter = GrpcStubPubSubAdapter(SimpleNamespace(Subscribe=responses))

        async def requests() -> AsyncIterator[dict[str, Any]]:
            yield {"topic_name": "/data/AccountChangeEvent"}

        stream = await adapter.subscribe(requests(), metadata={})

        assert [item async for item in stream] == [expected]

    async def test_accepts_synchronous_schema_method_returning_mapping(self) -> None:
        schema = '{"type":"record","name":"Account","fields":[]}'
        adapter = GrpcStubPubSubAdapter(
            SimpleNamespace(GetSchema=lambda request, **kwargs: {"schema_json": schema})
        )

        assert await adapter.get_schema_json("schema-1", metadata={}) == schema

    @pytest.mark.asyncio
    async def test_parses_generated_stream_and_schema_shapes(self) -> None:
        """Normalize generated response objects into CDC dict-shaped contracts."""
        stub = _FakeStub()
        adapter = GrpcStubPubSubAdapter(stub)

        async def _requests() -> AsyncIterator[dict[str, Any]]:
            yield {
                "topic_name": "/data/AccountChangeEvent",
                "replay_preset": "LATEST",
                "replay_id": None,
                "num_requested": 1,
            }

        stream = await adapter.subscribe(
            _requests(),
            metadata={"tenantid": "00Dxx"},
            timeout=5.0,
        )
        first = await anext(stream)
        schema_json = await adapter.get_schema_json(
            "schema-1",
            metadata={"tenantid": "00Dxx"},
            timeout=3.0,
        )

        assert first["latest_replay_id"] == 42
        assert first["events"][0]["event"]["schema_id"] == "schema-1"
        assert first["events"][0]["event"]["replay_id"] == 41
        assert schema_json == '{"name": "Account"}'
        assert stub.subscribe_calls[0]["metadata"] == (("tenantid", "00Dxx"),)
        assert stub.schema_calls[0]["request"] == {"schema_id": "schema-1"}

    @pytest.mark.asyncio
    async def test_raises_when_stub_methods_are_missing(self) -> None:
        """Raise clear errors when required generated-stub methods are missing."""

        class _MissingSubscribe:
            async def get_schema(
                self,
                request: dict[str, Any],
                **_: Any,
            ) -> dict[str, Any]:
                return request

        _MissingSubscribe.GetSchema = _MissingSubscribe.get_schema  # type: ignore[attr-defined]

        class _MissingSchema:
            def subscribe(
                self,
                requests: AsyncIterator[dict[str, Any]],
                **_: Any,
            ) -> AsyncIterator[dict[str, Any]]:
                return requests

        _MissingSchema.Subscribe = _MissingSchema.subscribe  # type: ignore[attr-defined]

        missing_subscribe = GrpcStubPubSubAdapter(_MissingSubscribe())
        missing_schema = GrpcStubPubSubAdapter(_MissingSchema())

        async def _requests() -> AsyncIterator[dict[str, Any]]:
            yield {"topic_name": "/data/AccountChangeEvent"}

        with pytest.raises(RuntimeError, match="does not implement Subscribe"):
            await missing_subscribe.subscribe(_requests(), metadata={})

        with pytest.raises(RuntimeError, match="does not implement GetSchema"):
            await missing_schema.get_schema_json("schema-1", metadata={})

    @pytest.mark.asyncio
    async def test_raises_when_schema_json_is_missing(self) -> None:
        """Raise clear errors for malformed schema responses."""

        class _BadSchemaStub:
            def __init__(self) -> None:
                self.schema_calls: list[dict[str, Any]] = []

            async def get_schema(
                self,
                request: dict[str, Any],
                *,
                metadata: tuple[tuple[str, str], ...] | None = None,
                timeout: float | None = None,
            ) -> dict[str, str]:
                self.schema_calls.append(
                    {
                        "request": request,
                        "metadata": metadata,
                        "timeout": timeout,
                    }
                )
                return {"unexpected": "value"}

        _BadSchemaStub.GetSchema = _BadSchemaStub.get_schema  # type: ignore[attr-defined]

        adapter = GrpcStubPubSubAdapter(_BadSchemaStub())

        with pytest.raises(RuntimeError, match="did not include schema_json"):
            await adapter.get_schema_json("schema-1", metadata={})


class TestVendoredStub:
    """Verify the adapter against plynt's real vendored generated stub.

    Unlike ``_FakeStub`` and friends above, these use the actual generated
    ``pubsub_api_pb2``/``pubsub_api_pb2_grpc`` classes, proving field names
    and types match Salesforce's real generated code rather than a
    hand-written approximation of its shape.
    """

    @pytest.mark.asyncio
    async def test_create_vendored_pubsub_adapter_builds_stub_from_channel(
        self,
    ) -> None:
        """Wire the vendored PubSubStub onto a channel via the factory."""
        channel = grpc.aio.insecure_channel("localhost:7443")
        try:
            adapter = create_vendored_pubsub_adapter(channel)
        finally:
            await channel.close()

        assert isinstance(adapter, GrpcStubPubSubAdapter)

    @pytest.mark.asyncio
    async def test_parses_real_generated_fetch_response(self) -> None:
        """Normalize a real ``pubsub_api_pb2.FetchResponse`` message."""
        real_response = pubsub_api_pb2.FetchResponse(
            latest_replay_id=(42).to_bytes(2, byteorder="big"),
            pending_num_requested=4,
            events=[
                pubsub_api_pb2.ConsumerEvent(
                    event=pubsub_api_pb2.ProducerEvent(
                        id="evt-1",
                        schema_id="schema-1",
                        payload=b"abc",
                    ),
                    replay_id=(41).to_bytes(2, byteorder="big"),
                )
            ],
        )

        parsed = GrpcStubPubSubAdapter._parse_fetch_response(real_response)

        assert parsed["latest_replay_id"] == 42
        assert parsed["pending_num_requested"] == 4
        assert parsed["events"][0]["event"]["schema_id"] == "schema-1"
        assert parsed["events"][0]["event"]["payload"] == b"abc"
        assert parsed["events"][0]["replay_id"] == 41

    def test_extracts_schema_json_from_real_schema_info(self) -> None:
        """Normalize a real ``pubsub_api_pb2.SchemaInfo`` response."""
        real_schema_info = pubsub_api_pb2.SchemaInfo(
            schema_json='{"type": "record"}',
            schema_id="schema-1",
        )

        schema_json = GrpcStubPubSubAdapter._extract_schema_json(real_schema_info)

        assert schema_json == '{"type": "record"}'

    def test_builds_real_fetch_request(self) -> None:
        """Confirm a real ``FetchRequest`` accepts the fields we populate."""
        request = pubsub_api_pb2.FetchRequest(
            topic_name="/data/AccountChangeEvent",
            replay_preset=pubsub_api_pb2.ReplayPreset.LATEST,
            num_requested=1,
        )

        assert request.topic_name == "/data/AccountChangeEvent"
        assert request.num_requested == 1
