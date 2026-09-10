"""Salesforce Pub/Sub adapter primitives for CDC orchestration.

The CDC subscriber consumes a small, dict-shaped contract for fetch responses
and schema lookup. This module bridges that contract to either:

1. method-based generic gRPC clients, or
2. generated Salesforce Pub/Sub stubs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from inspect import isawaitable
from typing import Any, Protocol

__all__ = [
    "GrpcMethodPubSubAdapter",
    "GrpcStubPubSubAdapter",
    "SalesforcePubSubAdapter",
    "create_vendored_pubsub_adapter",
]


class SalesforcePubSubAdapter(Protocol):
    """Protocol consumed by the CDC subscriber for Pub/Sub operations."""

    async def subscribe(
        self,
        requests: AsyncIterator[dict[str, Any]],
        *,
        metadata: dict[str, str],
        timeout: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Return a stream of normalized fetch responses."""

    async def get_schema_json(
        self,
        schema_id: str,
        *,
        metadata: dict[str, str],
        timeout: float | None = None,
    ) -> str:
        """Return schema JSON for one schema identifier."""


class _GrpcMethodClientProtocol(Protocol):
    """Protocol for method-based generic gRPC clients."""

    async def stream_stream(
        self,
        method: str,
        requests: AsyncIterator[dict[str, Any]],
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Execute a bidirectional streaming call."""

    async def unary_unary(
        self,
        method: str,
        request: dict[str, Any],
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Execute a unary request-response call."""


class GrpcMethodPubSubAdapter:
    """Adapt method-based generic gRPC calls to the Pub/Sub adapter contract."""

    def __init__(
        self,
        client: _GrpcMethodClientProtocol,
        *,
        subscribe_method: str,
        schema_method: str,
    ) -> None:
        """Initialize method-based adapter state."""
        self._client = client
        self._subscribe_method = subscribe_method
        self._schema_method = schema_method

    async def subscribe(
        self,
        requests: AsyncIterator[dict[str, Any]],
        *,
        metadata: dict[str, str],
        timeout: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Return a normalized stream from the configured Subscribe method."""
        upstream = await self._client.stream_stream(
            self._subscribe_method,
            requests,
            metadata=metadata,
            timeout=timeout,
        )

        async def _stream() -> AsyncIterator[dict[str, Any]]:
            async for response in upstream:
                if isinstance(response, dict):
                    yield response

        return _stream()

    async def get_schema_json(
        self,
        schema_id: str,
        *,
        metadata: dict[str, str],
        timeout: float | None = None,
    ) -> str:
        """Return schema JSON from the configured GetSchema method."""
        response = await self._client.unary_unary(
            self._schema_method,
            {"schema_id": schema_id},
            metadata=metadata,
            timeout=timeout,
        )
        if isinstance(response, dict):
            schema_json = response.get("schema_json")
            if isinstance(schema_json, str) and schema_json:
                return schema_json
        raise RuntimeError("Salesforce GetSchema response did not include schema_json")


FetchRequestFactory = Callable[[dict[str, Any]], Any]
FetchResponseParser = Callable[[Any], dict[str, Any]]
SchemaRequestFactory = Callable[[str], Any]
SchemaResponseExtractor = Callable[[Any], str]


class GrpcStubPubSubAdapter:
    """Adapt generated Salesforce Pub/Sub stubs to normalized CDC contracts."""

    def __init__(
        self,
        stub: Any,
        *,
        fetch_request_factory: FetchRequestFactory | None = None,
        fetch_response_parser: FetchResponseParser | None = None,
        schema_request_factory: SchemaRequestFactory | None = None,
        schema_response_extractor: SchemaResponseExtractor | None = None,
    ) -> None:
        """Initialize generated-stub adapter dependencies."""
        self._stub = stub
        self._fetch_request_factory = fetch_request_factory or (lambda value: value)
        self._fetch_response_parser = (
            fetch_response_parser or self._parse_fetch_response
        )
        self._schema_request_factory = schema_request_factory or (
            lambda schema_id: {"schema_id": schema_id}
        )
        self._schema_response_extractor = (
            schema_response_extractor or self._extract_schema_json
        )

    async def subscribe(
        self,
        requests: AsyncIterator[dict[str, Any]],
        *,
        metadata: dict[str, str],
        timeout: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Call generated Subscribe and normalize each response."""
        subscribe = getattr(self._stub, "Subscribe", None)
        if not callable(subscribe):
            raise RuntimeError("Salesforce Pub/Sub stub does not implement Subscribe")

        stream_or_awaitable = subscribe(
            self._build_fetch_request_stream(requests),
            metadata=self._to_grpc_metadata(metadata),
            timeout=timeout,
        )
        upstream = await self._await_if_needed(stream_or_awaitable)

        async def _stream() -> AsyncIterator[dict[str, Any]]:
            async for raw_response in upstream:
                yield self._fetch_response_parser(raw_response)

        return _stream()

    async def get_schema_json(
        self,
        schema_id: str,
        *,
        metadata: dict[str, str],
        timeout: float | None = None,
    ) -> str:
        """Call generated GetSchema and return normalized schema JSON."""
        get_schema = getattr(self._stub, "GetSchema", None)
        if not callable(get_schema):
            raise RuntimeError("Salesforce Pub/Sub stub does not implement GetSchema")

        response_or_awaitable = get_schema(
            self._schema_request_factory(schema_id),
            metadata=self._to_grpc_metadata(metadata),
            timeout=timeout,
        )
        response = await self._await_if_needed(response_or_awaitable)
        return self._schema_response_extractor(response)

    async def _build_fetch_request_stream(
        self,
        requests: AsyncIterator[dict[str, Any]],
    ) -> AsyncIterator[Any]:
        """Convert dict-shaped fetch requests into generated message objects."""
        async for request in requests:
            yield self._fetch_request_factory(request)

    @staticmethod
    async def _await_if_needed(value: Any) -> Any:
        """Await values that are awaitable and pass others through unchanged."""
        if isawaitable(value):
            return await value
        return value

    @staticmethod
    def _to_grpc_metadata(metadata: dict[str, str]) -> tuple[tuple[str, str], ...]:
        """Convert metadata mapping to gRPC metadata tuple shape."""
        return tuple(metadata.items())

    @staticmethod
    def _extract_schema_json(response: Any) -> str:
        """Extract schema JSON from dict or generated GetSchema response."""
        if isinstance(response, dict):
            schema_json = response.get("schema_json")
            if isinstance(schema_json, str) and schema_json:
                return schema_json

        schema_json_attr = getattr(response, "schema_json", None)
        if isinstance(schema_json_attr, str) and schema_json_attr:
            return schema_json_attr

        raise RuntimeError("Salesforce GetSchema response did not include schema_json")

    @staticmethod
    def _parse_fetch_response(response: Any) -> dict[str, Any]:
        """Normalize one generated FetchResponse into dict-shaped data."""
        if isinstance(response, dict):
            return response

        latest_replay_id = GrpcStubPubSubAdapter._coerce_replay_id(
            getattr(response, "latest_replay_id", None)
        )
        raw_events = getattr(response, "events", [])
        events = [
            parsed
            for parsed in (
                GrpcStubPubSubAdapter._parse_consumer_event(raw_event)
                for raw_event in raw_events
            )
            if parsed is not None
        ]

        return {
            "latest_replay_id": latest_replay_id,
            "events": events,
        }

    @staticmethod
    def _parse_consumer_event(raw_event: Any) -> dict[str, Any] | None:
        """Normalize one consumer event from a generated response."""
        if isinstance(raw_event, dict):
            return raw_event

        replay_id = GrpcStubPubSubAdapter._coerce_replay_id(
            getattr(raw_event, "replay_id", None)
        )
        payload = GrpcStubPubSubAdapter._parse_payload(
            getattr(raw_event, "event", None)
        )

        parsed_event: dict[str, Any] = {}
        if payload:
            parsed_event["event"] = payload
        if replay_id is not None:
            parsed_event["replay_id"] = replay_id
        if parsed_event:
            return parsed_event
        return None

    @staticmethod
    def _parse_payload(payload: Any) -> dict[str, Any]:
        """Normalize one generated event payload object."""
        if payload is None:
            return {}

        parsed_payload: dict[str, Any] = {}
        schema_id = getattr(payload, "schema_id", None)
        if isinstance(schema_id, str):
            parsed_payload["schema_id"] = schema_id

        payload_bytes = getattr(payload, "payload", None)
        if isinstance(payload_bytes, bytes):
            parsed_payload["payload"] = payload_bytes

        topic_name = getattr(payload, "topic_name", None)
        if isinstance(topic_name, str):
            parsed_payload["topic_name"] = topic_name

        payload_replay_id = GrpcStubPubSubAdapter._coerce_replay_id(
            getattr(payload, "replay_id", None)
        )
        if payload_replay_id is not None:
            parsed_payload["replay_id"] = payload_replay_id

        return parsed_payload

    @staticmethod
    def _coerce_replay_id(value: Any) -> int | None:
        """Coerce replay IDs from int/bytes-like values when possible."""
        if isinstance(value, int):
            return value
        if isinstance(value, (bytes, bytearray)):
            if not value:
                return 0
            return int.from_bytes(value, byteorder="big", signed=False)
        return None


def create_vendored_pubsub_adapter(channel: Any) -> GrpcStubPubSubAdapter:
    """Build a `GrpcStubPubSubAdapter` from plynth's vendored Pub/Sub stub.

    This wires the generated `eventbus.v1` stub vendored in
    `plynth.connectors.salesforce.cdc._proto` onto *channel*, so callers do
    not need to generate or import the Salesforce Pub/Sub protobuf stub
    themselves. Callers who need a custom-generated stub can still construct
    `GrpcStubPubSubAdapter` directly instead of using this factory.

    Args:
        channel: A `grpc.aio.Channel` (or compatible) connected to the
            Salesforce Pub/Sub endpoint.

    """
    # Imported lazily: grpc/protobuf are optional deps (the `grpc` extra),
    # and callers using GrpcMethodPubSubAdapter should not need them.
    from plynth.connectors.salesforce.cdc._proto import (
        pubsub_api_pb2_grpc,
    )

    return GrpcStubPubSubAdapter(pubsub_api_pb2_grpc.PubSubStub(channel))
