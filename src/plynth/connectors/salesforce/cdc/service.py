"""Async Salesforce CDC subscribe orchestration.

This module intentionally lives above the generic gRPC transport layer and below
any consumer-specific materialization logic. It translates Salesforce Pub/Sub
subscribe semantics into a typed CDC stream that is still generic across orgs
and instances.

Responsibilities kept here:

- Salesforce Pub/Sub auth metadata
- subscribe request shaping
- schema fetch orchestration and per-subscriber cache
- payload decoding via an injected decoder
- bounded reconnect with replay resume

Responsibilities kept out of this module:

- raw gRPC channel construction
- durable cursor storage
- shadow-store materialization
- tenant- or customer-specific CDC processing rules
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

from plynth.connectors.salesforce.cdc.models import (
    SalesforceCDCAuthMetadata,
    SalesforceCDCEnvelope,
    SalesforceCDCEvent,
    SalesforceCDCSubscribeRequest,
)
from plynth.connectors.salesforce.cdc.pubsub import (
    GrpcMethodPubSubAdapter,
    SalesforcePubSubAdapter,
)
from plynth.grpc.errors import GrpcStatusError, GrpcTransportError

__all__ = ["AsyncSalesforceCDCSubscriber"]


SchemaLoader = Callable[[str, dict[str, str]], Awaitable[str]]
PayloadDecoder = Callable[[str, bytes], dict[str, Any]]


class _GrpcClientProtocol(Protocol):
    """Small protocol describing the gRPC client features CDC needs."""

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


class _UnimplementedCDCStream(AsyncIterator[SalesforceCDCEvent]):
    """Raise a clear error when CDC iteration is attempted.

    This preserves a stable public object shape even before the subscriber is
    fully wired with transport, auth metadata, and decoding dependencies.
    """

    def __aiter__(self) -> _UnimplementedCDCStream:
        return self

    async def __anext__(self) -> SalesforceCDCEvent:
        raise NotImplementedError(
            "Salesforce CDC subscription transport is not implemented yet"
        )


# pylint: disable=too-few-public-methods
class AsyncSalesforceCDCSubscriber:
    """Subscribe to Salesforce CDC channels through the Pub/Sub API.

    The subscriber follows the same essential pattern as Salesforce's Python
    quick start, but adapts it to plynth's package boundaries:

    - generic gRPC transport in ``plynth.grpc``
    - Salesforce-specific metadata, schema fetch, and CDC mapping here
    - downstream replication logic outside the connector
    """

    def __init__(
        self,
        client: _GrpcClientProtocol | None = None,
        *,
        pubsub: SalesforcePubSubAdapter | None = None,
        auth_metadata: SalesforceCDCAuthMetadata | None = None,
        auth_metadata_provider: (
            Callable[[], Awaitable[SalesforceCDCAuthMetadata]] | None
        ) = None,
        schema_loader: SchemaLoader | None = None,
        payload_decoder: PayloadDecoder | None = None,
        subscribe_method: str = "/eventbus.v1.PubSub/Subscribe",
        schema_method: str = "/eventbus.v1.PubSub/GetSchema",
        reconnect_max_attempts: int = 3,
    ) -> None:
        """Initialize the CDC subscriber orchestration.

        Args:
            client: Generic async gRPC client used for Subscribe and GetSchema
                when ``pubsub`` is not supplied.
            pubsub: Optional Salesforce Pub/Sub adapter. When supplied, this
                becomes the canonical Subscribe/GetSchema integration surface.
            auth_metadata: Static Salesforce Pub/Sub auth metadata.
            auth_metadata_provider: Async provider for auth metadata when the
                values are fetched lazily.
            schema_loader: Optional injected schema loader for tests or custom
                schema retrieval behavior.
            payload_decoder: Decoder that turns Avro payload bytes plus schema
                JSON into a Python ``dict``.
            subscribe_method: Fully qualified Subscribe RPC method name.
            schema_method: Fully qualified GetSchema RPC method name.
            reconnect_max_attempts: Bounded reconnect budget after stream
                interruption.

        """
        self._client = client
        self._pubsub = pubsub
        self._auth_metadata = auth_metadata
        self._auth_metadata_provider = auth_metadata_provider
        self._payload_decoder = payload_decoder
        self._subscribe_method = subscribe_method
        self._schema_method = schema_method
        self._reconnect_max_attempts = reconnect_max_attempts
        self._schema_cache: dict[str, str] = {}
        if self._pubsub is None and client is not None:
            self._pubsub = GrpcMethodPubSubAdapter(
                client,
                subscribe_method=subscribe_method,
                schema_method=schema_method,
            )
        self._schema_loader = schema_loader or self._load_schema

    async def subscribe(
        self,
        request: SalesforceCDCSubscribeRequest,
    ) -> AsyncIterator[SalesforceCDCEvent]:
        """Return a typed CDC event stream for a subscription request.

        When the subscriber has not been fully wired yet, it falls back to the
        placeholder stream so the public contract remains importable and
        testable during phased implementation.
        """
        if self._pubsub is None or self._payload_decoder is None:
            return _UnimplementedCDCStream()

        metadata = await self._resolve_metadata()
        return self._subscribe_with_reconnect(request, metadata)

    async def _subscribe_with_reconnect(
        self,
        request: SalesforceCDCSubscribeRequest,
        metadata: dict[str, str],
    ) -> AsyncIterator[SalesforceCDCEvent]:
        """Subscribe with bounded reconnect using the latest replay cursor.

        A reconnect attempt resumes from the latest replay cursor that was
        observed in a successful response. If the stream breaks before any
        cursor is known, the subscriber fails clearly because a safe resume
        point does not exist yet.
        """
        pubsub = self._pubsub
        if pubsub is None:
            return

        replay_id = request.replay_id
        attempts = 0

        while True:
            resumed_request = request.model_copy(update={"replay_id": replay_id})
            try:
                stream = await pubsub.subscribe(
                    self._fetch_request_stream(resumed_request),
                    metadata=metadata,
                )
                # Each reconnect replays the same orchestration path: subscribe,
                # decode envelopes, update the latest replay cursor, and yield
                # typed CDC events downstream.
                async for event, latest_replay_id in self._event_stream(
                    stream,
                    metadata,
                ):
                    if latest_replay_id is not None:
                        replay_id = latest_replay_id
                    attempts = 0
                    yield event
                return
            except (GrpcStatusError, GrpcTransportError) as exc:
                if replay_id is None:
                    raise RuntimeError(
                        "Salesforce CDC stream interrupted before a replay "
                        "cursor was established"
                    ) from exc
                if attempts >= self._reconnect_max_attempts:
                    raise RuntimeError(
                        "Salesforce CDC reconnect attempts exhausted"
                    ) from exc
                attempts += 1

    async def _event_stream(
        self,
        stream: AsyncIterator[Any],
        metadata: dict[str, str],
    ) -> AsyncIterator[tuple[SalesforceCDCEvent, int | None]]:
        """Yield typed CDC events from a raw Subscribe response stream.

        The extra replay-id return value keeps reconnect concerns local to this
        service without leaking reconnect state into the public event model.
        """
        async for response in stream:
            latest_replay_id = self._extract_latest_replay_id(response)
            for raw_event in self._extract_events(response):
                event = await self._to_cdc_event(
                    raw_event,
                    metadata=metadata,
                    latest_replay_id=latest_replay_id,
                )
                if event is not None:
                    yield event, latest_replay_id

    async def _to_cdc_event(
        self,
        raw_event: Any,
        *,
        metadata: dict[str, str],
        latest_replay_id: int | None,
    ) -> SalesforceCDCEvent | None:
        """Map a raw Pub/Sub consumer event into a typed CDC event.

        The payload decoder is intentionally injected so Avro decoding strategy
        can evolve without forcing that concern into the generic gRPC layer.
        """
        event_data = self._extract_event_payload(raw_event)
        schema_id = event_data.get("schema_id")
        payload_bytes = event_data.get("payload")
        if not isinstance(schema_id, str) or not isinstance(payload_bytes, bytes):
            return None

        decoder = self._payload_decoder
        if decoder is None:
            return None

        schema_json = await self._get_schema(schema_id, metadata)
        decoded_payload = decoder(schema_json, payload_bytes)
        # Pub/Sub delivers a decoded record body plus ChangeEventHeader-style
        # metadata. The public CDC event keeps those parts separate as
        # envelope-vs-payload for downstream consumers.
        header = decoded_payload.get("ChangeEventHeader", {})
        if not isinstance(header, dict):
            header = {}

        object_name = self._coerce_string(
            header.get("entityName"),
            fallback=self._derive_object_name(event_data.get("topic_name")),
        )
        envelope = SalesforceCDCEnvelope(
            channel=self._coerce_string(
                event_data.get("topic_name"),
                fallback=object_name,
            ),
            object_name=object_name,
            replay_id=self._coerce_int(
                event_data.get("replay_id"),
                fallback=latest_replay_id,
            ),
            event_type=self._coerce_string(
                header.get("changeType"),
                fallback="UNKNOWN",
            ),
            change_type=self._coerce_string(
                header.get("changeType"),
                fallback="UNKNOWN",
            ),
            record_ids=self._coerce_string_list(header.get("recordIds")),
            schema_id=schema_id,
            change_origin=self._coerce_optional_string(header.get("changeOrigin")),
            commit_number=self._coerce_optional_int(header.get("commitNumber")),
            commit_timestamp=self._coerce_optional_int(header.get("commitTimestamp")),
            commit_user=self._coerce_optional_string(header.get("commitUser")),
            transaction_key=self._coerce_optional_string(header.get("transactionKey")),
            sequence_number=self._coerce_optional_int(header.get("sequenceNumber")),
            changed_fields=self._coerce_string_list(header.get("changedFields")),
            nulled_fields=self._coerce_string_list(header.get("nulledFields")),
            diff_fields=self._coerce_string_list(header.get("diffFields")),
        )
        payload = {
            key: value
            for key, value in decoded_payload.items()
            if key != "ChangeEventHeader"
        }
        return SalesforceCDCEvent(envelope=envelope, payload=payload)

    async def _resolve_metadata(self) -> dict[str, str]:
        """Resolve Salesforce Pub/Sub authentication metadata."""
        if self._auth_metadata is not None:
            return self._auth_metadata.to_metadata()
        if self._auth_metadata_provider is None:
            raise RuntimeError(
                "Salesforce CDC subscriber requires auth metadata or a provider"
            )
        return (await self._auth_metadata_provider()).to_metadata()

    async def _get_schema(
        self,
        schema_id: str,
        metadata: dict[str, str],
    ) -> str:
        """Return schema JSON for an event schema ID with per-instance caching."""
        if schema_id not in self._schema_cache:
            self._schema_cache[schema_id] = await self._schema_loader(
                schema_id,
                metadata,
            )
        return self._schema_cache[schema_id]

    async def _load_schema(self, schema_id: str, metadata: dict[str, str]) -> str:
        """Load schema JSON through the generic gRPC client contract."""
        pubsub = self._pubsub
        if pubsub is None:
            raise RuntimeError("Salesforce CDC subscriber requires a Pub/Sub adapter")
        return await pubsub.get_schema_json(
            schema_id,
            metadata=metadata,
        )

    async def _fetch_request_stream(
        self,
        request: SalesforceCDCSubscribeRequest,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield FetchRequest-like dictionaries for the subscribe stream.

        The request shape mirrors the Salesforce quick start at a logical level:
        topic name, replay strategy, replay cursor, and fetch size.
        """
        yield {
            "topic_name": request.channel,
            "replay_preset": "CUSTOM" if request.replay_id is not None else "LATEST",
            "replay_id": request.replay_id,
            "num_requested": request.num_requested,
        }

    @staticmethod
    def _extract_latest_replay_id(response: Any) -> int | None:
        """Extract the latest replay ID from a raw FetchResponse."""
        if isinstance(response, dict):
            return AsyncSalesforceCDCSubscriber._coerce_optional_int(
                response.get("latest_replay_id")
            )
        return None

    @staticmethod
    def _extract_events(response: Any) -> list[Any]:
        """Extract raw consumer events from a raw FetchResponse."""
        if isinstance(response, dict):
            events = response.get("events", [])
            if isinstance(events, list):
                return events
        return []

    @staticmethod
    def _extract_event_payload(raw_event: Any) -> dict[str, Any]:
        """Normalize raw consumer events into a dict-like payload container."""
        if isinstance(raw_event, dict):
            event_payload = raw_event.get("event")
            if isinstance(event_payload, dict):
                normalized = dict(event_payload)
                if "replay_id" not in normalized and "replay_id" in raw_event:
                    normalized["replay_id"] = raw_event["replay_id"]
                return normalized
            return dict(raw_event)
        return {}

    @staticmethod
    def _derive_object_name(topic_name: Any) -> str:
        """Derive the object name from a CDC topic path when possible."""
        if not isinstance(topic_name, str) or not topic_name:
            return "Unknown"
        name = topic_name.rsplit("/", maxsplit=1)[-1]
        if name.endswith("ChangeEvent"):
            return name[: -len("ChangeEvent")]
        return name

    @staticmethod
    def _coerce_int(value: Any, *, fallback: int | None = None) -> int:
        """Coerce a value to int with an optional fallback."""
        if isinstance(value, int):
            return value
        if fallback is not None:
            return fallback
        return 0

    @staticmethod
    def _coerce_optional_int(value: Any) -> int | None:
        """Coerce an optional integer-like value."""
        if isinstance(value, int):
            return value
        return None

    @staticmethod
    def _coerce_string(value: Any, *, fallback: str) -> str:
        """Coerce a value to a string with a required fallback."""
        if isinstance(value, str) and value:
            return value
        return fallback

    @staticmethod
    def _coerce_optional_string(value: Any) -> str | None:
        """Coerce an optional string-like value."""
        if isinstance(value, str) and value:
            return value
        return None

    @staticmethod
    def _coerce_string_list(value: Any) -> list[str]:
        """Coerce a list of strings while dropping non-string entries."""
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]
