"""Focused contract tests for the Salesforce CDC subscriber.

These tests intentionally use small fake gRPC client doubles instead of real
generated Pub/Sub stubs. The goal is to validate plynt's orchestration logic:
metadata shaping, schema loading, payload decoding, and bounded reconnect.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest

from plynt.connectors.salesforce.cdc import (
    AsyncSalesforceCDCAuthMetadataProvider,
    AsyncSalesforceCDCSubscriber,
    InMemorySalesforceCDCCheckpointStore,
    SalesforceCDCAuthMetadata,
    SalesforceCDCGapError,
    SalesforceCDCOverflowError,
    SalesforceCDCSubscribeRequest,
)
from plynt.connectors.salesforce.cdc.service import _CheckpointingCDCStream
from plynt.grpc.errors import GrpcTransportError


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
        captured_requests = [await anext(requests)]
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


class _FakeAsyncOAuthAuth:
    """Small auth double for CDC auth metadata provider integration."""

    async def _get_token_header(self) -> dict[str, str]:
        return {"Authorization": "Bearer token-123"}

    async def get_instance_url(self) -> str:
        return "https://example.my.salesforce.com/"


class _EventRecorder:
    """Collect subscriber observability events for assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, name: str, details: dict[str, Any]) -> None:
        self.events.append((name, details))


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

    async def test_explicit_close_flushes_checkpoint_and_closes_stream(self) -> None:
        store = InMemorySalesforceCDCCheckpointStore()
        subscriber = AsyncSalesforceCDCSubscriber(
            _FakeAsyncGrpcClient(),
            checkpoint_store=store,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )
        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        assert aiter(stream) is stream
        event = await anext(stream)
        assert store.load(event.channel) is None

        assert isinstance(stream, _CheckpointingCDCStream)
        await stream.aclose()

        assert store.load(event.channel) == event.replay_id
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
        await subscriber.shutdown()

    async def test_shutdown_from_subscribe_observer_prevents_rpc_start(self) -> None:
        client = _FakeAsyncGrpcClient()
        observations: list[str] = []

        async def observer(name: str, details: dict[str, Any]) -> None:
            observations.append(name)
            if name == "subscribe_started":
                await subscriber.shutdown()

        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            observer=observer,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )
        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        assert [event async for event in stream] == []
        assert not client.stream_calls
        assert "stream_stopped" in observations

    async def test_shutdown_from_reconnect_observer_prevents_retry(self) -> None:
        client = _FakeAsyncGrpcClient(
            [_StreamPlan(responses=[], error=GrpcTransportError("connection lost"))]
        )
        observations: list[str] = []

        async def observer(name: str, details: dict[str, Any]) -> None:
            observations.append(name)
            if name == "reconnect_attempt":
                await subscriber.shutdown()

        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            observer=observer,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )
        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(
                channel="/data/AccountChangeEvent", replay_id=42
            )
        )

        assert [event async for event in stream] == []
        assert len(client.stream_calls) == 1
        assert "reconnect_attempt" in observations
        assert observations[-1] == "stream_stopped"

    async def test_shutdown_while_receiving_response_discards_late_events(self) -> None:
        observations = _EventRecorder()
        response = _default_stream_plan().responses[0]

        class LateResponseStream:
            def __aiter__(self) -> LateResponseStream:
                return self

            async def __anext__(self) -> dict[str, Any]:
                await subscriber.shutdown()
                return response

        class LateResponseClient(_FakeAsyncGrpcClient):
            async def stream_stream(
                self,
                method: str,
                requests: AsyncIterator[dict[str, Any]],
                *,
                metadata: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> AsyncIterator[dict[str, Any]]:
                await anext(requests)
                return LateResponseStream()

        client = LateResponseClient()
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            observer=observations,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )
        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        assert [event async for event in stream] == []
        assert not client.unary_calls
        assert observations.events[-1] == ("stream_stopped", {"reason": "shutdown"})

    async def test_shutdown_after_skipped_event_stops_remaining_batch(self) -> None:
        response = _default_stream_plan().responses[0]
        response["events"].insert(0, {})
        client = _FakeAsyncGrpcClient([_StreamPlan(responses=[response])])

        async def observer(name: str, details: dict[str, Any]) -> None:
            if name == "decode_skipped":
                assert details == {"reason": "missing_payload"}
                await subscriber.shutdown()

        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            observer=observer,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )
        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        assert [event async for event in stream] == []
        assert not client.unary_calls

    async def test_non_mapping_response_does_not_report_gap_or_overflow(self) -> None:
        observations = _EventRecorder()
        subscriber = AsyncSalesforceCDCSubscriber(observer=observations)

        await subscriber._raise_for_gap_or_overflow(None)

        assert not observations.events

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
        assert event.envelope.changed_fields == ["Amount"]
        assert event.envelope.nulled_fields == ["Type"]
        assert event.envelope.diff_fields == []
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
    async def test_subscribe_accepts_auth_metadata_provider_from_auth_middleware(
        self,
    ) -> None:
        """Resolve CDC metadata through the auth middleware adapter."""
        client = _FakeAsyncGrpcClient()
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata_provider=AsyncSalesforceCDCAuthMetadataProvider(
                _FakeAsyncOAuthAuth(),
                tenant_id="00Dxx0000000001",
            ),
            payload_decoder=_payload_decoder,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        await anext(stream)

        assert client.stream_calls[0]["metadata"] == {
            "accesstoken": "token-123",
            "instanceurl": "https://example.my.salesforce.com",
            "tenantid": "00Dxx0000000001",
        }

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

        assert aiter(stream) is stream

        with pytest.raises(
            NotImplementedError,
            match="Salesforce CDC subscription transport is not implemented yet",
        ):
            await anext(stream)

    @pytest.mark.asyncio
    async def test_subscribe_stops_cleanly_when_stream_is_exhausted(self) -> None:
        """Finish iteration cleanly when the upstream stream ends normally."""
        client = _FakeAsyncGrpcClient()
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        first = await anext(stream)

        assert first.replay_id == 42
        with pytest.raises(StopAsyncIteration):
            await anext(stream)

    @pytest.mark.asyncio
    async def test_shutdown_stops_active_stream_cleanly(self) -> None:
        """Close the active stream cooperatively when shutdown is requested."""
        observer = _EventRecorder()
        client = _FakeAsyncGrpcClient()
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            observer=observer,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        await subscriber.shutdown()

        with pytest.raises(StopAsyncIteration):
            await anext(stream)
        assert observer.events[-2:] == [
            ("shutdown_requested", {}),
            ("shutdown_completed", {}),
        ]

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

    @pytest.mark.asyncio
    async def test_subscribe_requires_auth_metadata_when_wired(self) -> None:
        """Raise clearly when the subscriber is wired but auth metadata is missing."""
        subscriber = AsyncSalesforceCDCSubscriber(
            _FakeAsyncGrpcClient(),
            payload_decoder=_payload_decoder,
        )

        with pytest.raises(
            RuntimeError,
            match="requires auth metadata or a provider",
        ):
            await subscriber.subscribe(
                SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
            )

    @pytest.mark.asyncio
    async def test_resumes_from_checkpoint_store_when_request_has_no_replay_id(
        self,
    ) -> None:
        """Use a stored replay cursor when the request does not set one."""
        store = InMemorySalesforceCDCCheckpointStore({"/data/AccountChangeEvent": 77})
        client = _FakeAsyncGrpcClient()
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            checkpoint_store=store,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        await anext(stream)

        assert client.stream_calls[0]["requests"] == [
            {
                "topic_name": "/data/AccountChangeEvent",
                "replay_preset": "CUSTOM",
                "replay_id": 77,
                "num_requested": 1,
            }
        ]

    @pytest.mark.asyncio
    async def test_checkpoints_only_after_consumer_advances_stream(self) -> None:
        """Persist the delivered replay cursor only after the next pull."""
        observer = _EventRecorder()
        store = InMemorySalesforceCDCCheckpointStore()
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
                                },
                                {
                                    "event": {
                                        "schema_id": "schema-123",
                                        "payload": b"payload-1",
                                        "topic_name": "/data/AccountChangeEvent",
                                        "replay_id": 43,
                                    }
                                },
                            ],
                        }
                    ]
                )
            ]
        )
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            checkpoint_store=store,
            observer=observer,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        first = await anext(stream)
        assert first.replay_id == 42
        assert store.load("/data/AccountChangeEvent") is None

        second = await anext(stream)
        assert second.replay_id == 43
        assert store.load("/data/AccountChangeEvent") == 42

        with pytest.raises(StopAsyncIteration):
            await anext(stream)
        assert store.load("/data/AccountChangeEvent") == 43
        assert (
            "schema_cache_miss",
            {"schema_id": "schema-123"},
        ) in observer.events
        assert (
            "schema_cache_hit",
            {"schema_id": "schema-123"},
        ) in observer.events
        assert (
            "checkpoint_saved",
            {"replay_id": 42},
        ) in observer.events
        assert (
            "checkpoint_saved",
            {"replay_id": 43},
        ) in observer.events

    @pytest.mark.asyncio
    async def test_fails_clearly_when_stream_reports_gap_event(self) -> None:
        """Fail fast when the normalized response reports a replay gap."""
        client = _FakeAsyncGrpcClient(
            stream_plans=[
                _StreamPlan(
                    responses=[
                        {
                            "gap": True,
                            "latest_replay_id": 42,
                            "error_message": "checkpoint is too old",
                        }
                    ]
                )
            ]
        )
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        with pytest.raises(
            SalesforceCDCGapError,
            match=r"replay gap.*latest_replay_id=42.*checkpoint is too old",
        ):
            await anext(stream)
        assert not client.unary_calls

    @pytest.mark.asyncio
    async def test_emits_gap_observation_before_raising(self) -> None:
        """Emit a gap observation before surfacing the gap exception."""
        observer = _EventRecorder()
        client = _FakeAsyncGrpcClient(
            stream_plans=[
                _StreamPlan(
                    responses=[
                        {
                            "gap": True,
                            "latest_replay_id": 42,
                            "error_message": "checkpoint is too old",
                        }
                    ]
                )
            ]
        )
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            observer=observer,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        with pytest.raises(SalesforceCDCGapError):
            await anext(stream)

        assert (
            "gap_detected",
            {
                "latest_replay_id": 42,
                "error_message": "checkpoint is too old",
            },
        ) in observer.events

    @pytest.mark.asyncio
    async def test_fails_clearly_when_stream_reports_overflow_event(self) -> None:
        """Fail fast when the normalized response reports an overflow event."""
        client = _FakeAsyncGrpcClient(
            stream_plans=[
                _StreamPlan(
                    responses=[
                        {
                            "overflow": True,
                            "latest_replay_id": 99,
                        }
                    ]
                )
            ]
        )
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        with pytest.raises(
            SalesforceCDCOverflowError,
            match=r"overflow event.*latest_replay_id=99",
        ):
            await anext(stream)
        assert not client.unary_calls

    @pytest.mark.asyncio
    async def test_caches_schema_by_schema_id(self) -> None:
        """Load one schema once even when multiple events reuse the same ID."""
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
                                },
                                {
                                    "event": {
                                        "schema_id": "schema-123",
                                        "payload": b"payload-1",
                                        "topic_name": "/data/AccountChangeEvent",
                                    }
                                },
                            ],
                        }
                    ]
                )
            ]
        )
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        await anext(stream)
        await anext(stream)

        assert len(client.unary_calls) == 1

    @pytest.mark.asyncio
    async def test_skips_events_without_schema_or_payload(self) -> None:
        """Skip malformed consumer events that cannot be decoded safely."""
        client = _FakeAsyncGrpcClient(
            stream_plans=[
                _StreamPlan(
                    responses=[
                        {
                            "latest_replay_id": 42,
                            "events": [
                                {"event": {"topic_name": "/data/AccountChangeEvent"}},
                                {
                                    "schema_id": "schema-123",
                                    "topic_name": "/data/AccountChangeEvent",
                                },
                            ],
                        }
                    ]
                )
            ]
        )
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )

        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        with pytest.raises(StopAsyncIteration):
            await anext(stream)
        assert not client.unary_calls

    @pytest.mark.asyncio
    async def test_skips_events_when_decoder_is_missing_during_mapping(self) -> None:
        """Return no mapped event when decode support disappears unexpectedly."""
        subscriber = AsyncSalesforceCDCSubscriber(
            _FakeAsyncGrpcClient(),
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )
        subscriber._payload_decoder = None  # pylint: disable=protected-access

        event = await subscriber._to_cdc_event(  # pylint: disable=protected-access
            {
                "event": {
                    "schema_id": "schema-123",
                    "payload": b"payload-1",
                    "topic_name": "/data/AccountChangeEvent",
                }
            },
            metadata={"accesstoken": "x"},
            latest_replay_id=42,
        )

        assert event is None

    @pytest.mark.asyncio
    async def test_subscribe_with_reconnect_stops_immediately_without_client(
        self,
    ) -> None:
        """Return an empty stream when reconnect logic is called without a client."""
        subscriber = AsyncSalesforceCDCSubscriber()
        stream = subscriber._subscribe_with_reconnect(  # pylint: disable=protected-access
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent"),
            {"accesstoken": "x"},
        )

        with pytest.raises(StopAsyncIteration):
            await anext(stream)

    @pytest.mark.asyncio
    async def test_non_dict_header_falls_back_to_unknown_metadata(self) -> None:
        """Handle decoded payloads whose ChangeEventHeader is not a mapping."""

        def _bad_header_decoder(
            _schema_json: str,
            _payload: bytes,
        ) -> dict[str, Any]:
            return {
                "ChangeEventHeader": "bad-header",
                "Id": "001xx000003GYWJAA4",
            }

        subscriber = AsyncSalesforceCDCSubscriber(
            _FakeAsyncGrpcClient(),
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_bad_header_decoder,
        )

        event = await subscriber._to_cdc_event(  # pylint: disable=protected-access
            {
                "event": {
                    "schema_id": "schema-123",
                    "payload": b"payload-1",
                    "topic_name": "/data/ChangeEvents",
                },
                "replay_id": 7,
            },
            metadata={"accesstoken": "x"},
            latest_replay_id=42,
        )

        assert event is not None
        assert event.envelope.object_name == "ChangeEvents"
        assert event.envelope.event_type == "UNKNOWN"
        assert event.replay_id == 7

    def test_helper_branches_cover_direct_values_and_topic_derivation(self) -> None:
        """Exercise direct helper branches not hit by end-to-end stream tests."""
        subscriber = AsyncSalesforceCDCSubscriber()

        assert subscriber._extract_event_payload(  # pylint: disable=protected-access
            {"event": {"schema_id": "schema-123"}, "replay_id": 55}
        ) == {"schema_id": "schema-123", "replay_id": 55}
        assert (
            subscriber._derive_object_name(  # pylint: disable=protected-access
                "/data/AccountChangeEvent"
            )
            == "Account"
        )
        assert subscriber._coerce_int(9) == 9  # pylint: disable=protected-access

    @pytest.mark.asyncio
    async def test_load_schema_requires_client(self) -> None:
        """Fail clearly when GetSchema is attempted without a gRPC client."""
        subscriber = AsyncSalesforceCDCSubscriber()

        with pytest.raises(RuntimeError, match="requires a Pub/Sub adapter"):
            await subscriber._load_schema(  # pylint: disable=protected-access
                "schema-123",
                {"accesstoken": "x"},
            )

    @pytest.mark.asyncio
    async def test_load_schema_requires_schema_json_in_response(self) -> None:
        """Fail clearly when GetSchema returns a payload without schema_json."""

        class _BadSchemaClient(_FakeAsyncGrpcClient):
            async def unary_unary(
                self,
                method: str,
                request: dict[str, Any],
                *,
                metadata: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> dict[str, str]:
                self.unary_calls.append(
                    {
                        "method": method,
                        "request": request,
                        "metadata": metadata,
                        "timeout": timeout,
                    }
                )
                return {"unexpected": "value"}

        subscriber = AsyncSalesforceCDCSubscriber(
            _BadSchemaClient(),
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )

        with pytest.raises(
            RuntimeError,
            match="did not include schema_json",
        ):
            await subscriber._load_schema(  # pylint: disable=protected-access
                "schema-123",
                {"accesstoken": "x"},
            )

    def test_helper_coercions_cover_fallback_paths(self) -> None:
        """Exercise fallback behavior for the small coercion helpers."""
        subscriber = AsyncSalesforceCDCSubscriber()

        assert subscriber._extract_latest_replay_id([]) is None  # pylint: disable=protected-access
        assert subscriber._extract_events({"events": "bad"}) == []  # pylint: disable=protected-access
        assert subscriber._extract_event_payload({"event": "bad"}) == {"event": "bad"}  # pylint: disable=protected-access
        assert not subscriber._extract_event_payload("bad")  # pylint: disable=protected-access
        assert subscriber._derive_object_name(None) == "Unknown"  # pylint: disable=protected-access
        assert subscriber._coerce_int("bad", fallback=5) == 5  # pylint: disable=protected-access
        assert subscriber._coerce_int("bad") == 0  # pylint: disable=protected-access
        assert subscriber._coerce_optional_int("bad") is None  # pylint: disable=protected-access
        assert subscriber._coerce_string("", fallback="UNKNOWN") == "UNKNOWN"  # pylint: disable=protected-access
        assert subscriber._coerce_optional_string(123) is None  # pylint: disable=protected-access
        assert subscriber._coerce_string_list("bad") == []  # pylint: disable=protected-access

    def test_stream_error_suffix_formats_optional_context(self) -> None:
        """Render stable diagnostics for normalized gap or overflow signals."""
        subscriber = AsyncSalesforceCDCSubscriber()

        assert subscriber._format_stream_error_suffix(42, "detail") == (  # pylint: disable=protected-access
            " (latest_replay_id=42; detail)"
        )
        assert subscriber._format_stream_error_suffix(None, None) == ""  # pylint: disable=protected-access

    def test_default_checkpoint_key_uses_channel(self) -> None:
        """Default checkpoint keys align to one CDC channel path."""
        subscriber = AsyncSalesforceCDCSubscriber()

        assert (
            subscriber._default_checkpoint_key(  # pylint: disable=protected-access
                SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
            )
            == "/data/AccountChangeEvent"
        )

    @pytest.mark.asyncio
    async def test_decodes_header_bitmaps_using_the_event_schema(self) -> None:
        """Expose actual field names rather than Salesforce bitmap strings."""
        schema_json = (
            '{"type":"record","name":"Account","fields":['
            '{"name":"ChangeEventHeader","type":"string"},'
            '{"name":"Name","type":"string"},'
            '{"name":"Description","type":["null","string"]},'
            '{"name":"Address","type":["null",{"type":"record","name":"Address",'
            '"fields":[{"name":"City","type":"string"},'
            '{"name":"Street","type":"string"}]}]}]}'
        )

        async def _schema_loader(_schema_id: str, _metadata: dict[str, str]) -> str:
            return schema_json

        def _decoder(_schema: str, _payload: bytes) -> dict[str, Any]:
            return {
                "ChangeEventHeader": {
                    "entityName": "Account",
                    "changeType": "UPDATE",
                    "changedFields": ["0x06", "3-0x01"],
                    "nulledFields": ["3-0x02"],
                    "diffFields": ["0x04"],
                },
                "Name": "New name",
                "Description": "A diff",
                "Address": {"City": "Utrecht", "Street": None},
            }

        subscriber = AsyncSalesforceCDCSubscriber(
            _FakeAsyncGrpcClient(),
            auth_metadata_provider=_auth_metadata_provider,
            schema_loader=_schema_loader,
            payload_decoder=_decoder,
        )
        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )
        try:
            event = await anext(stream)
            assert event.envelope.changed_fields == [
                "Name",
                "Description",
                "Address.City",
            ]
            assert event.envelope.nulled_fields == ["Address.Street"]
            assert event.envelope.diff_fields == ["Description"]
        finally:
            await subscriber.shutdown()

    @pytest.mark.asyncio
    async def test_replenishes_custom_adapter_without_pending_count(
        self,
    ) -> None:
        """Count delivered events for adapters without Salesforce credit metadata"""

        class _RequestDrivenClient(_FakeAsyncGrpcClient):
            async def stream_stream(
                self,
                method: str,
                requests: AsyncIterator[dict[str, Any]],
                *,
                metadata: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> AsyncIterator[dict[str, Any]]:
                async def _stream() -> AsyncIterator[dict[str, Any]]:
                    self.stream_calls.append(await anext(requests))
                    yield {
                        "events": [
                            {"event": {}},
                            {"event": {}},
                        ]
                    }
                    self.stream_calls.append(await anext(requests))
                    yield _default_stream_plan().responses[0]

                return _stream()

        client = _RequestDrivenClient()
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )
        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(
                channel="/data/AccountChangeEvent", num_requested=2
            )
        )
        try:
            event = await anext(stream)
            assert event.replay_id == 42
            assert client.stream_calls == [
                {
                    "topic_name": "/data/AccountChangeEvent",
                    "replay_preset": "LATEST",
                    "replay_id": None,
                    "num_requested": 2,
                },
                {"topic_name": "/data/AccountChangeEvent", "num_requested": 2},
            ]
        finally:
            await subscriber.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pending", [-1, 101, "0", True])
    async def test_rejects_invalid_pending_count_without_reconnecting(
        self, pending: Any
    ) -> None:
        """Surface malformed flow-control metadata instead of refilling blindly"""
        client = _FakeAsyncGrpcClient(
            [_StreamPlan(responses=[{"events": [], "pending_num_requested": pending}])]
        )
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )
        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )
        try:
            with pytest.raises(RuntimeError, match="invalid pending_num_requested"):
                await anext(stream)
            assert len(client.stream_calls) == 1
        finally:
            await subscriber.shutdown()

    @pytest.mark.asyncio
    async def test_reconnect_does_not_skip_unprocessed_events_in_a_batch(self) -> None:
        """Resume from the last consumed event if schema loading fails mid-batch"""

        class _TransientSchemaClient(_FakeAsyncGrpcClient):
            async def unary_unary(
                self,
                method: str,
                request: dict[str, Any],
                *,
                metadata: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> dict[str, str]:
                if request["schema_id"] == "schema-new" and len(self.stream_calls) == 1:
                    raise GrpcTransportError("schema RPC interrupted")
                return await super().unary_unary(
                    method, request, metadata=metadata, timeout=timeout
                )

        client = _TransientSchemaClient(
            [
                _StreamPlan(
                    responses=[
                        {
                            "latest_replay_id": 50,
                            "pending_num_requested": 0,
                            "events": [
                                {
                                    "replay_id": 41,
                                    "event": {
                                        "schema_id": "schema-123",
                                        "payload": b"payload-1",
                                    },
                                },
                                {
                                    "replay_id": 42,
                                    "event": {
                                        "schema_id": "schema-new",
                                        "payload": b"payload-1",
                                    },
                                },
                            ],
                        }
                    ]
                ),
                _default_stream_plan(),
            ]
        )
        subscriber = AsyncSalesforceCDCSubscriber(
            client,
            auth_metadata_provider=_auth_metadata_provider,
            payload_decoder=_payload_decoder,
        )
        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(
                channel="/data/AccountChangeEvent", num_requested=2
            )
        )
        try:
            first = await anext(stream)
            second = await anext(stream)
            assert [first.replay_id, second.replay_id] == [41, 42]
            assert client.stream_calls[1]["requests"][0]["replay_id"] == 41
        finally:
            await subscriber.shutdown()
