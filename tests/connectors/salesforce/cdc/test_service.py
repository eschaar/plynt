"""Focused contract tests for the Salesforce CDC subscriber.

These tests intentionally use small fake gRPC client doubles instead of real
generated Pub/Sub stubs. The goal is to validate plynth's orchestration logic:
metadata shaping, schema loading, payload decoding, and bounded reconnect.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest

from plynth.connectors.salesforce.cdc import (
    AsyncSalesforceCDCSubscriber,
    SalesforceCDCAuthMetadata,
    SalesforceCDCSubscribeRequest,
)
from plynth.grpc.errors import GrpcTransportError


class _FakeAsyncGrpcClient:
    """Small gRPC client double used to exercise CDC orchestration logic."""

    def __init__(self, stream_plans: list[_StreamPlan] | None = None) -> None:
        """Initialize the fake client with deterministic stream plans."""
        self.stream_calls: list[dict[str, Any]] = []
        self.unary_calls: list[dict[str, Any]] = []
        self._stream_plans = list(stream_plans or [_default_stream_plan()])

    async def stream_stream(
        self,
        method: str,
        requests: AsyncIterator[dict[str, Any]],
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Record Subscribe calls and replay a planned response stream."""
        captured_requests = [request async for request in requests]
        self.stream_calls.append(
            {
                "method": method,
                "requests": captured_requests,
                "metadata": metadata,
                "timeout": timeout,
            }
        )
        plan = self._stream_plans.pop(0)

        async def _stream() -> AsyncIterator[dict[str, Any]]:
            # Each plan represents one Subscribe attempt. Tests can inject an
            # error at the tail to exercise reconnect behavior deterministically.
            for response in plan.responses:
                yield response
            if plan.error is not None:
                raise plan.error

        return _stream()

    async def unary_unary(
        self,
        method: str,
        request: dict[str, Any],
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, str]:
        """Record GetSchema calls and return deterministic schema JSON."""
        self.unary_calls.append(
            {
                "method": method,
                "request": request,
                "metadata": metadata,
                "timeout": timeout,
            }
        )
        return {"schema_json": '{"type": "record", "name": "Account"}'}


@dataclass
class _StreamPlan:
    """Describe one fake Subscribe attempt and its terminal behavior."""

    responses: list[dict[str, Any]]
    error: Exception | None = None


def _default_stream_plan() -> _StreamPlan:
    """Return the default happy-path Subscribe response plan."""
    return _StreamPlan(
        responses=[
            {
                "latest_replay_id": 42,
                "events": [
                    {
                        "event": {
                            "schema_id": "schema-123",
                            "payload": b"payload-1",
                            "topic_name": "/data/AccountChangeEvent",
                        }
                    }
                ],
            }
        ]
    )


async def _auth_metadata_provider() -> SalesforceCDCAuthMetadata:
    """Return deterministic Salesforce Pub/Sub auth metadata for tests."""
    return SalesforceCDCAuthMetadata(
        access_token="token-123",
        instance_url="https://example.my.salesforce.com",
        tenant_id="00Dxx0000000001",
    )


def _payload_decoder(schema_json: str, payload: bytes) -> dict[str, Any]:
    """Decode a deterministic fake payload into a CDC-style record body."""
    assert schema_json == '{"type": "record", "name": "Account"}'
    assert payload == b"payload-1"
    return {
        "ChangeEventHeader": {
            "entityName": "Account",
            "recordIds": ["001xx000003GYWJAA4"],
            "changeType": "UPDATE",
            "changeOrigin": "com/salesforce/api/rest/67.0",
            "transactionKey": "tx-123",
            "sequenceNumber": 1,
            "commitTimestamp": 1712693965000,
            "commitNumber": 1082985383811,
            "commitUser": "005xx0000000001AAA",
            "nulledFields": ["Type"],
            "diffFields": [],
            "changedFields": ["Amount"],
        },
        "Amount": 110000,
        "LastModifiedDate": 1712693965000,
    }


class TestAsyncSalesforceCDCSubscriber:
    """Test suite for the async CDC subscriber skeleton."""

    def test_subscribe_contract_accepts_only_generic_request(self) -> None:
        """Keep the async contract focused on a generic subscription request."""
        signature = inspect.signature(AsyncSalesforceCDCSubscriber.subscribe)

        assert list(signature.parameters) == ["self", "request"]
        assert signature.return_annotation is not inspect.Signature.empty

    @pytest.mark.asyncio
    async def test_subscribe_yields_typed_cdc_events(self) -> None:
        """Build typed CDC events from Salesforce-style Subscribe responses."""
        client = _FakeAsyncGrpcClient()
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )
        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(
                channel="/data/AccountChangeEvent",
                num_requested=1,
            )
        )

        event = await anext(stream)

        assert event.channel == "/data/AccountChangeEvent"
        assert event.replay_id == 42
        assert event.envelope.object_name == "Account"
        assert event.envelope.record_ids == ["001xx000003GYWJAA4"]
        assert event.payload["Amount"] == 110000
        assert client.stream_calls[0]["requests"] == [
            {
                "topic_name": "/data/AccountChangeEvent",
                "replay_preset": "LATEST",
                "replay_id": None,
                "num_requested": 1,
            }
        ]
        assert client.stream_calls[0]["metadata"] == {
            "accesstoken": "token-123",
            "instanceurl": "https://example.my.salesforce.com",
            "tenantid": "00Dxx0000000001",
        }
        assert client.unary_calls[0]["request"] == {"schema_id": "schema-123"}

    @pytest.mark.asyncio
    async def test_subscribe_uses_custom_replay_when_replay_id_is_supplied(
        self,
    ) -> None:
        """Switch to a custom replay preset when a replay ID is supplied."""
        client = _FakeAsyncGrpcClient()
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata=SalesforceCDCAuthMetadata(
                access_token="token-123",
                instance_url="https://example.my.salesforce.com",
                tenant_id="00Dxx0000000001",
            ),
            payload_decoder=_payload_decoder,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(
                channel="/data/AccountChangeEvent",
                replay_id=99,
                num_requested=5,
            )
        )

        await anext(stream)

        assert client.stream_calls[0]["requests"] == [
            {
                "topic_name": "/data/AccountChangeEvent",
                "replay_preset": "CUSTOM",
                "replay_id": 99,
                "num_requested": 5,
            }
        ]

    @pytest.mark.asyncio
    async def test_subscribe_falls_back_to_placeholder_without_runtime_dependencies(
        self,
    ) -> None:
        """Keep current placeholder behavior when dependencies are missing."""
        subscriber = AsyncSalesforceCDCSubscriber()
        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        with pytest.raises(
            NotImplementedError,
            match="Salesforce CDC subscription transport is not implemented yet",
        ):
            await anext(stream)

    @pytest.mark.asyncio
    async def test_reconnects_with_latest_replay_id_after_stream_failure(self) -> None:
        """Resume with the last replay cursor when a stream fails mid-flight."""
        client = _FakeAsyncGrpcClient(
            stream_plans=[
                _StreamPlan(
                    responses=[
                        {
                            "latest_replay_id": 42,
                            "events": [
                                {
                                    "event": {
                                        "schema_id": "schema-123",
                                        "payload": b"payload-1",
                                        "topic_name": "/data/AccountChangeEvent",
                                    }
                                }
                            ],
                        }
                    ],
                    error=GrpcTransportError("stream disconnected"),
                ),
                _StreamPlan(
                    responses=[
                        {
                            "latest_replay_id": 43,
                            "events": [
                                {
                                    "event": {
                                        "schema_id": "schema-123",
                                        "payload": b"payload-1",
                                        "topic_name": "/data/AccountChangeEvent",
                                    }
                                }
                            ],
                        }
                    ]
                ),
            ]
        )
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
            reconnect_max_attempts=1,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        first = await anext(stream)
        second = await anext(stream)

        assert first.replay_id == 42
        assert second.replay_id == 43
        assert client.stream_calls[1]["requests"] == [
            {
                "topic_name": "/data/AccountChangeEvent",
                "replay_preset": "CUSTOM",
                "replay_id": 42,
                "num_requested": 1,
            }
        ]

    @pytest.mark.asyncio
    async def test_fails_clearly_when_stream_breaks_before_replay_cursor(self) -> None:
        """Fail clearly when the stream breaks before a replay cursor exists."""
        client = _FakeAsyncGrpcClient(
            stream_plans=[
                _StreamPlan(
                    responses=[],
                    error=GrpcTransportError("boom"),
                )
            ]
        )
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
            reconnect_max_attempts=1,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        with pytest.raises(
            RuntimeError,
            match="replay cursor was established",
        ):
            await anext(stream)

    @pytest.mark.asyncio
    async def test_fails_clearly_when_reconnect_attempts_are_exhausted(self) -> None:
        """Fail clearly when reconnect cannot resume within the retry budget."""
        client = _FakeAsyncGrpcClient(
            stream_plans=[
                _StreamPlan(
                    responses=[],
                    error=GrpcTransportError("boom"),
                )
            ]
        )
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
            reconnect_max_attempts=0,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(
                channel="/data/AccountChangeEvent",
                replay_id=99,
            )
        )

        with pytest.raises(
            RuntimeError,
            match="reconnect attempts exhausted",
        ):
            await anext(stream)
