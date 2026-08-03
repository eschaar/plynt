"""Focused tests for Salesforce CDC Pub/Sub adapter primitives."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest

from plynth.connectors.salesforce.cdc.pubsub import (
    GrpcMethodPubSubAdapter,
    GrpcStubPubSubAdapter,
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
