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

from collections.abc import AsyncIterator
from typing import Any

import grpc
import pytest

from plynth.connectors.salesforce.cdc import (
    AsyncSalesforceCDCAuthMetadataProvider,
    AsyncSalesforceCDCSubscriber,
    SalesforceCDCSubscribeRequest,
    create_vendored_pubsub_adapter,
)
from plynth.connectors.salesforce.cdc._proto import (
    pubsub_api_pb2,
    pubsub_api_pb2_grpc,
)

_SCHEMA_JSON = '{"type": "record", "name": "Account", "fields": []}'


class _FakePubSubServicer(pubsub_api_pb2_grpc.PubSubServicer):
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
