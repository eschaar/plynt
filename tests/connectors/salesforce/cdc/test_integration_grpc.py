"""End-to-end test: vendored Pub/Sub stub over a real in-process gRPC server.

Unlike the fake/dataclass doubles used elsewhere in this package, this test
exercises the *real* generated protobuf classes, real gRPC wire serialization,
and a real Salesforce auth middleware instance. It closes two gaps that unit
tests with hand-written doubles cannot:

1. Whether ``create_vendored_pubsub_adapter`` produces request objects the
   real generated stub can actually serialize (it previously did not —
   see the fix in ``pubsub.py``: request dicts must become real
   ``FetchRequest``/``SchemaRequest`` messages, not pass through as dicts).
2. Whether ``AsyncSalesforceCDCAuthMetadataProvider`` really resolves auth
   metadata from a real async Salesforce auth middleware instance, not just
   a hand-written fake double.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import grpc
import pytest

from plynth.connectors.salesforce.cdc import (
    AsyncSalesforceCDCAuthMetadataProvider,
    AsyncSalesforceCDCSubscriber,
    InMemorySalesforceCDCCheckpointStore,
    SalesforceCDCReplayInvalidError,
    SalesforceCDCSubscribeRequest,
    create_vendored_pubsub_adapter,
)
from plynth.connectors.salesforce.cdc._proto import (
    pubsub_api_pb2,
    pubsub_api_pb2_grpc,
)

_SCHEMA_JSON = '{"type": "record", "name": "Account", "fields": []}'


class _FakePubSubServicer(pubsub_api_pb2_grpc.PubSubServicer):  # type: ignore[misc]
    """In-process fake Salesforce Pub/Sub server for wire-level testing."""

    def __init__(self) -> None:
        """Initialize call recordings."""
        self.received_metadata: dict[str, str] = {}
        self.received_requests: list[pubsub_api_pb2.FetchRequest] = []
        self.schema_requests: list[str] = []

    async def Subscribe(  # noqa: N802 - generated RPC method name
        self,
        request_iterator: AsyncIterator[pubsub_api_pb2.FetchRequest],
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[pubsub_api_pb2.FetchResponse]:
        """Record one real FetchRequest and reply with one real FetchResponse."""
        self.received_metadata = dict(context.invocation_metadata() or ())
        async for request in request_iterator:
            self.received_requests.append(request)
            yield pubsub_api_pb2.FetchResponse(
                latest_replay_id=(42).to_bytes(8, byteorder="big"),
                events=[
                    pubsub_api_pb2.ConsumerEvent(
                        event=pubsub_api_pb2.ProducerEvent(
                            id="evt-1",
                            schema_id="schema-123",
                            payload=b"payload-bytes",
                        ),
                        replay_id=(42).to_bytes(8, byteorder="big"),
                    )
                ],
            )
            return

    async def GetSchema(  # noqa: N802 - generated RPC method name
        self,
        request: pubsub_api_pb2.SchemaRequest,
        context: grpc.aio.ServicerContext,
    ) -> pubsub_api_pb2.SchemaInfo:
        """Record the schema ID and reply with a real SchemaInfo message."""
        self.schema_requests.append(request.schema_id)
        return pubsub_api_pb2.SchemaInfo(
            schema_json=_SCHEMA_JSON,
            schema_id=request.schema_id,
        )


def _payload_decoder(schema_json: str, payload: bytes) -> dict[str, Any]:
    """Decode a deterministic fake payload, asserting the real schema JSON."""
    assert schema_json == _SCHEMA_JSON
    assert payload == b"payload-bytes"
    return {
        "ChangeEventHeader": {
            "entityName": "Account",
            "recordIds": ["001xx000003GYWJAA4"],
            "changeType": "UPDATE",
        },
        "Amount": 42,
    }


class TestVendoredPubSubGrpcIntegration:
    """Exercise the vendored stub end-to-end against a real gRPC server."""

    @pytest.mark.asyncio
    async def test_subscribe_over_real_grpc_with_real_auth_middleware(
        self,
        make_async_salesforce_auth: Any,
    ) -> None:
        """Subscribe end-to-end using real serialization and real auth."""
        servicer = _FakePubSubServicer()
        server = grpc.aio.server()
        pubsub_api_pb2_grpc.add_PubSubServicer_to_server(servicer, server)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()

        auth = make_async_salesforce_auth()
        channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
        subscriber = AsyncSalesforceCDCSubscriber(
            pubsub=create_vendored_pubsub_adapter(channel),
            auth_metadata_provider=AsyncSalesforceCDCAuthMetadataProvider(
                auth, tenant_id="00Dxx0000000001"
            ),
            payload_decoder=_payload_decoder,
        )

        try:
            stream = await subscriber.subscribe(
                SalesforceCDCSubscribeRequest(
                    channel="/data/AccountChangeEvent", num_requested=1
                )
            )
            event = await anext(stream)
        finally:
            await subscriber.shutdown()
            await channel.close()
            await server.stop(None)

        assert event.replay_id == 42
        assert event.envelope.object_name == "Account"
        assert event.payload["Amount"] == 42
        assert servicer.schema_requests == ["schema-123"]
        assert servicer.received_requests[0].topic_name == "/data/AccountChangeEvent"
        assert servicer.received_requests[0].num_requested == 1
        assert servicer.received_metadata["accesstoken"]
        assert servicer.received_metadata["instanceurl"]
        assert servicer.received_metadata["tenantid"] == "00Dxx0000000001"

    @pytest.mark.asyncio
    async def test_requests_more_events_on_the_same_grpc_stream(
        self,
        make_async_salesforce_auth: Any,
    ) -> None:
        """Receive multiple batches without ending the request stream."""
        async with _flow_subscription(make_async_salesforce_auth()) as (
            subscriber,
            servicer,
        ):
            stream = await subscriber.subscribe(
                SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
            )
            async with asyncio.timeout(3):
                first = await anext(stream)
                second = await anext(stream)
                third = await anext(stream)
            assert [first.replay_id, second.replay_id, third.replay_id] == [42, 43, 44]
            assert len(servicer.received_requests) == 3
            assert [
                request.num_requested for request in servicer.received_requests
            ] == [1, 1, 1]

    @pytest.mark.asyncio
    async def test_partial_batches_and_keepalives_do_not_prefetch(
        self, make_async_salesforce_auth: Any
    ) -> None:
        """Wait until every event in a split batch is consumed before refilling"""
        store = InMemorySalesforceCDCCheckpointStore()
        async with _flow_subscription(
            make_async_salesforce_auth(),
            response_sizes=(1, 2),
            keepalive=True,
            checkpoint_store=store,
        ) as (subscriber, servicer):
            stream = await subscriber.subscribe(
                SalesforceCDCSubscribeRequest(
                    channel="/data/AccountChangeEvent", replay_id=20, num_requested=3
                )
            )
            async with asyncio.timeout(3):
                first = await anext(stream)
                assert len(servicer.received_requests) == 1
                second = await anext(stream)
                assert len(servicer.received_requests) == 1
                third = await anext(stream)
                assert len(servicer.received_requests) == 1
                assert store.load("/data/AccountChangeEvent") == second.replay_id
                fourth = await anext(stream)
            assert [
                first.replay_id,
                second.replay_id,
                third.replay_id,
                fourth.replay_id,
            ] == [42, 43, 44, 45]
            assert store.load("/data/AccountChangeEvent") == third.replay_id
            initial, refill = servicer.received_requests
            assert initial.replay_preset == pubsub_api_pb2.ReplayPreset.CUSTOM
            assert initial.replay_id == (20).to_bytes(8, "big")
            assert refill.replay_id == b""
            assert refill.num_requested == 3
            await subscriber.shutdown()
            assert store.load("/data/AccountChangeEvent") == fourth.replay_id
            await asyncio.wait_for(servicer.finished.wait(), timeout=3)

    @pytest.mark.asyncio
    async def test_caps_requested_batches_at_salesforce_limit(
        self, make_async_salesforce_auth: Any
    ) -> None:
        """Preserve large request inputs while limiting each wire request to 100"""
        async with _flow_subscription(make_async_salesforce_auth()) as (
            subscriber,
            servicer,
        ):
            stream = await subscriber.subscribe(
                SalesforceCDCSubscribeRequest(
                    channel="/data/AccountChangeEvent", num_requested=1000
                )
            )
            async with asyncio.timeout(3):
                events = [await anext(stream) for _ in range(101)]
            assert len(events) == 101
            assert [
                request.num_requested for request in servicer.received_requests
            ] == [100, 100]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("with_checkpoint_store", [False, True])
    async def test_shutdown_cancels_an_idle_rpc_and_pending_read(
        self, make_async_salesforce_auth: Any, with_checkpoint_store: bool
    ) -> None:
        """Stop an idle bidirectional stream without leaving request tasks alive"""
        store = InMemorySalesforceCDCCheckpointStore()
        async with _flow_subscription(
            make_async_salesforce_auth(),
            response_sizes=(0,),
            checkpoint_store=store if with_checkpoint_store else None,
        ) as (subscriber, servicer):
            stream = await subscriber.subscribe(
                SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
            )
            reader = asyncio.ensure_future(anext(stream))
            async with asyncio.timeout(3):
                await servicer.requests_seen.get()
                await subscriber.shutdown()
                with pytest.raises(StopAsyncIteration):
                    await reader
                await servicer.finished.wait()
            assert len(servicer.received_requests) == 1
            assert store.load("/data/AccountChangeEvent") is None

    @pytest.mark.asyncio
    async def test_cancelling_consumer_closes_the_upstream_rpc(
        self, make_async_salesforce_auth: Any
    ) -> None:
        """Propagate consumer cancellation and stop the corresponding gRPC call"""
        async with _flow_subscription(
            make_async_salesforce_auth(), response_sizes=(0,)
        ) as (subscriber, servicer):
            stream = await subscriber.subscribe(
                SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
            )
            reader = asyncio.ensure_future(anext(stream))
            async with asyncio.timeout(3):
                await servicer.requests_seen.get()
                reader.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await reader
                await servicer.finished.wait()

    @pytest.mark.asyncio
    async def test_reconnect_starts_a_fresh_request_stream_and_replenishes(
        self, make_async_salesforce_auth: Any
    ) -> None:
        """Resume after a real RPC failure and keep fetching on the new stream"""
        async with _flow_subscription(
            make_async_salesforce_auth(), disconnect_once=True
        ) as (subscriber, servicer):
            stream = await subscriber.subscribe(
                SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
            )
            async with asyncio.timeout(3):
                first = await anext(stream)
                second = await anext(stream)
                third = await anext(stream)
            assert [first.replay_id, second.replay_id, third.replay_id] == [42, 43, 44]
            initial, resumed, refill = servicer.received_requests
            assert initial.replay_id == b""
            assert resumed.replay_preset == pubsub_api_pb2.ReplayPreset.CUSTOM
            assert resumed.replay_id == (42).to_bytes(8, "big")
            assert refill.replay_id == b""


class _FlowControlledPubSubServicer(_FakePubSubServicer):
    """Deliver another event only after receiving another FetchRequest."""

    def __init__(
        self,
        *,
        response_sizes: tuple[int, ...] | None = None,
        keepalive: bool = False,
        disconnect_once: bool = False,
    ) -> None:
        super().__init__()
        self._response_sizes = response_sizes
        self._keepalive = keepalive
        self._disconnect_once = disconnect_once
        self._replay_id = 41
        self.requests_seen: asyncio.Queue[pubsub_api_pb2.FetchRequest] = asyncio.Queue()
        self.finished = asyncio.Event()

    async def Subscribe(  # noqa: N802
        self,
        request_iterator: AsyncIterator[pubsub_api_pb2.FetchRequest],
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[pubsub_api_pb2.FetchResponse]:
        """Keep the bidirectional stream open between successive requests."""
        try:
            async for request in request_iterator:
                self.received_requests.append(request)
                self.requests_seen.put_nowait(request)
                pending = request.num_requested
                if self._keepalive:
                    yield pubsub_api_pb2.FetchResponse(
                        pending_num_requested=pending,
                        latest_replay_id=self._replay_id.to_bytes(8, "big"),
                    )
                for size in self._response_sizes or (pending,):
                    events = []
                    for _ in range(size):
                        self._replay_id += 1
                        events.append(
                            pubsub_api_pb2.ConsumerEvent(
                                event=pubsub_api_pb2.ProducerEvent(
                                    schema_id="schema-123", payload=b"payload-bytes"
                                ),
                                replay_id=self._replay_id.to_bytes(8, "big"),
                            )
                        )
                    pending -= size
                    yield pubsub_api_pb2.FetchResponse(
                        pending_num_requested=pending,
                        latest_replay_id=self._replay_id.to_bytes(8, "big"),
                        events=events,
                    )
                if self._disconnect_once:
                    self._disconnect_once = False
                    await context.abort(grpc.StatusCode.UNAVAILABLE, "Disconnected")
        finally:
            self.finished.set()


@asynccontextmanager
async def _flow_subscription(
    auth: Any,
    *,
    response_sizes: tuple[int, ...] | None = None,
    keepalive: bool = False,
    checkpoint_store: InMemorySalesforceCDCCheckpointStore | None = None,
    disconnect_once: bool = False,
) -> AsyncIterator[tuple[AsyncSalesforceCDCSubscriber, _FlowControlledPubSubServicer]]:
    """Connect a real subscriber to a request-driven local Pub/Sub server"""
    servicer = _FlowControlledPubSubServicer(
        response_sizes=response_sizes,
        keepalive=keepalive,
        disconnect_once=disconnect_once,
    )
    server = grpc.aio.server()
    pubsub_api_pb2_grpc.add_PubSubServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    subscriber = AsyncSalesforceCDCSubscriber(
        pubsub=create_vendored_pubsub_adapter(channel),
        auth_metadata_provider=AsyncSalesforceCDCAuthMetadataProvider(
            auth, tenant_id="00Dxx0000000001"
        ),
        checkpoint_store=checkpoint_store,
        payload_decoder=_payload_decoder,
    )
    try:
        yield subscriber, servicer
    finally:
        await subscriber.shutdown()
        await channel.close()
        await server.stop(None)


class _ReplayInvalidPubSubServicer(pubsub_api_pb2_grpc.PubSubServicer):  # type: ignore[misc]
    """Fake server that rejects Subscribe like an expired/invalid replay ID."""

    async def Subscribe(  # noqa: N802 - generated RPC method name
        self,
        request_iterator: AsyncIterator[pubsub_api_pb2.FetchRequest],
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[pubsub_api_pb2.FetchResponse]:
        """Abort exactly like Salesforce's replayid.corrupted error."""
        async for _request in request_iterator:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "The Replay ID validation failed.",
            )
            return
        return
        yield  # pragma: no cover - makes this an async generator


class TestVendoredPubSubReplayInvalid:
    """Verify real INVALID_ARGUMENT errors map to a clear, non-retryable error."""

    @pytest.mark.asyncio
    async def test_invalid_replay_id_raises_replay_invalid_error(
        self,
        make_async_salesforce_auth: Any,
    ) -> None:
        """A real INVALID_ARGUMENT Subscribe error surfaces as a clear error."""
        server = grpc.aio.server()
        pubsub_api_pb2_grpc.add_PubSubServicer_to_server(
            _ReplayInvalidPubSubServicer(), server
        )
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()

        auth = make_async_salesforce_auth()
        channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
        subscriber = AsyncSalesforceCDCSubscriber(
            pubsub=create_vendored_pubsub_adapter(channel),
            auth_metadata_provider=AsyncSalesforceCDCAuthMetadataProvider(
                auth, tenant_id="00Dxx0000000001"
            ),
            payload_decoder=_payload_decoder,
        )

        try:
            stream = await subscriber.subscribe(
                SalesforceCDCSubscribeRequest(
                    channel="/data/AccountChangeEvent",
                    replay_id=123,
                    num_requested=1,
                )
            )
            with pytest.raises(SalesforceCDCReplayInvalidError):
                await anext(stream)
        finally:
            await subscriber.shutdown()
            await channel.close()
            await server.stop(None)
