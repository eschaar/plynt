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

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from inspect import isawaitable
from typing import Any, Protocol, cast

from plynth.connectors.salesforce.cdc._bitmap import _FieldBitmapDecoder
from plynth.connectors.salesforce.cdc.checkpoint import SalesforceCDCCheckpointStore
from plynth.connectors.salesforce.cdc.errors import (
    SalesforceCDCGapError,
    SalesforceCDCOverflowError,
    SalesforceCDCReplayInvalidError,
)
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
from plynth.grpc.transport import GrpcAioTransport

__all__ = [
    "AsyncSalesforceCDCSubscriber",
]


SchemaLoader = Callable[[str, dict[str, str]], Awaitable[str]]
PayloadDecoder = Callable[[str, bytes], dict[str, Any]]
CheckpointKeyBuilder = Callable[[SalesforceCDCSubscribeRequest], str]
ObservationCallback = Callable[[str, dict[str, Any]], object]
CloseCallback = Callable[[], object]


def _resolve_close_method(value: Any) -> CloseCallback | None:
    """Return a typed ``aclose`` callback when one exists on *value*."""
    close_method = getattr(value, "aclose", None)
    if callable(close_method):
        return cast(CloseCallback, close_method)
    return None


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


class _FetchRequestStream(AsyncIterator[dict[str, Any]]):
    """Coordinate bounded fetch requests with downstream event consumption

    The gRPC request reader and CDC response consumer run independently.
    ``_ready`` connects them: the first request is immediately available,
    then the request reader waits until ``processed`` observes a completed
    batch. Closing wakes that reader so it cannot remain blocked.

    A batch can span several responses. Server-reported pending credits
    take precedence over counting received events; an empty keepalive with
    outstanding credits does not refill the batch. Credits are replenished
    only after the consumer advances past every event in the response,
    preserving the connector-local backpressure policy from SF-0013.

    Args:
        request: Subscription parameters. Batch size is capped at Salesforce's
            100-event limit; replay selection is sent only on the first request.

    """

    def __init__(self, request: SalesforceCDCSubscribeRequest) -> None:
        self._request = request
        self._batch_size = min(request.num_requested, 100)
        self._remaining = self._batch_size
        self._ready = asyncio.Event()
        self._ready.set()
        self._initial = True
        self._closed = False

    def __aiter__(self) -> _FetchRequestStream:
        return self

    async def __anext__(self) -> dict[str, Any]:
        await self._ready.wait()
        self._ready.clear()
        if self._closed:
            raise StopAsyncIteration
        request: dict[str, Any] = {
            "topic_name": self._request.channel,
            "num_requested": self._batch_size,
        }
        if self._initial:
            request.update(
                replay_preset=(
                    "CUSTOM" if self._request.replay_id is not None else "LATEST"
                ),
                replay_id=self._request.replay_id,
            )
            self._initial = False
        return request

    def processed(self, response: Any, event_count: int) -> None:
        """Update outstanding credits after a response has been consumed

        Args:
            response: Normalized FetchResponse. Its ``pending_num_requested``
                value is authoritative when supplied by the adapter.
            event_count: Number of raw events received, including events
                skipped by decoding. Used when the adapter omits pending credits.

        Raises:
            RuntimeError: If reported pending credits are not an integer
                between zero and the requested batch size.

        """
        pending = (
            response.get("pending_num_requested")
            if isinstance(response, dict)
            else None
        )
        if pending is not None:
            if type(pending) is not int or not 0 <= pending <= self._batch_size:
                raise RuntimeError(
                    "Salesforce FetchResponse has invalid pending_num_requested"
                )
            self._remaining = pending
        else:
            self._remaining = max(0, self._remaining - event_count)
        if self._remaining == 0 and not self._closed:
            self._remaining = self._batch_size
            self._ready.set()

    async def aclose(self) -> None:
        """Wake and finish the request iterator when its subscription ends"""
        self._closed = True
        self._ready.set()


class _CheckpointingCDCStream(AsyncIterator[SalesforceCDCEvent]):
    """Checkpoint replay cursors only after the caller advanced the stream.

    This preserves at-least-once delivery semantics: a replay cursor is stored
    only when the consumer asks for the next item or when the stream ends.
    Explicit close also flushes the last delivered cursor. A pending read
    must finish through upstream cancellation rather than ``aclose`` on an
    executing async generator.
    """

    def __init__(
        self,
        stream: AsyncIterator[SalesforceCDCEvent],
        *,
        checkpoint_store: SalesforceCDCCheckpointStore,
        stream_key: str,
        on_checkpoint_saved: Callable[[int], object] | None = None,
    ) -> None:
        """Initialize checkpointing wrapper state."""
        self._stream = stream
        self._checkpoint_store = checkpoint_store
        self._stream_key = stream_key
        self._pending_replay_id: int | None = None
        self._on_checkpoint_saved = on_checkpoint_saved
        self._reading = False

    def __aiter__(self) -> _CheckpointingCDCStream:
        return self

    async def __anext__(self) -> SalesforceCDCEvent:
        self._flush_pending()
        self._reading = True
        try:
            event = await anext(self._stream)
        except StopAsyncIteration:
            self._flush_pending()
            raise
        finally:
            self._reading = False
        self._pending_replay_id = event.replay_id
        return event

    def _flush_pending(self) -> None:
        """Persist the last delivered replay cursor once it is acknowledged."""
        if self._pending_replay_id is None:
            return
        self._checkpoint_store.save(self._stream_key, self._pending_replay_id)
        on_checkpoint_saved = self._on_checkpoint_saved
        if on_checkpoint_saved is not None:
            on_checkpoint_saved(self._pending_replay_id)
        self._pending_replay_id = None

    async def aclose(self) -> None:
        """Flush pending state and close the wrapped stream when possible."""
        self._flush_pending()
        if self._reading:
            return
        close_method = _resolve_close_method(self._stream)
        if close_method is not None:
            result = close_method()
            if isawaitable(result):
                await result


# pylint: disable=too-few-public-methods,too-many-instance-attributes
class AsyncSalesforceCDCSubscriber:
    """Subscribe to Salesforce CDC channels through the Pub/Sub API.

    The subscriber follows the same essential pattern as Salesforce's Python
    quick start, but adapts it to plynth's package boundaries:

    - generic gRPC transport in ``plynth.grpc``
    - Salesforce-specific metadata, schema fetch, and CDC mapping here
    - downstream replication logic outside the connector

    Advance the returned iterator only after processing the previous event.
    Advancing acknowledges that event for checkpointing and permits a new
    fetch batch once all events in the current batch have been consumed.
    Header bitmaps are expanded with the event's Avro schema before delivery.
    """

    # The subscriber intentionally centralizes all CDC orchestration concerns
    # for one stream surface, so its constructor stays explicit rather than
    # hiding dependencies in nested config objects.
    # pylint: disable=too-many-arguments
    def __init__(
        self,
        client: _GrpcClientProtocol | None = None,
        *,
        pubsub: SalesforcePubSubAdapter | None = None,
        checkpoint_store: SalesforceCDCCheckpointStore | None = None,
        checkpoint_key_builder: CheckpointKeyBuilder | None = None,
        auth_metadata: SalesforceCDCAuthMetadata | None = None,
        auth_metadata_provider: (
            Callable[[], Awaitable[SalesforceCDCAuthMetadata]] | None
        ) = None,
        observer: ObservationCallback | None = None,
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
            checkpoint_store: Optional replay cursor checkpoint store.
            checkpoint_key_builder: Optional builder for checkpoint stream keys.
            auth_metadata: Static Salesforce Pub/Sub auth metadata.
            auth_metadata_provider: Async provider for auth metadata when the
                values are fetched lazily.
            observer: Optional callback receiving lightweight lifecycle and
                observability events.
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
        self._checkpoint_store = checkpoint_store
        self._checkpoint_key_builder = (
            checkpoint_key_builder or self._default_checkpoint_key
        )
        self._auth_metadata = auth_metadata
        self._auth_metadata_provider = auth_metadata_provider
        self._observer = observer
        self._payload_decoder = payload_decoder
        self._subscribe_method = subscribe_method
        self._schema_method = schema_method
        self._reconnect_max_attempts = reconnect_max_attempts
        self._schema_cache: dict[str, str] = {}
        self._field_bitmap_decoder = _FieldBitmapDecoder()
        self._stop_requested = False
        self._active_stream: Any | None = None
        self._active_response_stream: Any | None = None
        self._active_requests: _FetchRequestStream | None = None
        self._reading = False
        if self._pubsub is None and client is not None:
            self._pubsub = GrpcMethodPubSubAdapter(
                client,
                subscribe_method=subscribe_method,
                schema_method=schema_method,
            )
        self._schema_loader = schema_loader or self._load_schema

    async def shutdown(self) -> None:
        """Request cooperative stream shutdown and close the active stream."""
        self._stop_requested = True
        await self._emit_observation("shutdown_requested")

        if self._active_requests is not None:
            await self._active_requests.aclose()
        await self._close_stream(self._active_response_stream)

        active_stream = self._active_stream
        if active_stream is None:
            await self._emit_observation("shutdown_completed")
            return

        close_method = _resolve_close_method(active_stream)
        if close_method is not None and (
            not self._reading or isinstance(active_stream, _CheckpointingCDCStream)
        ):
            result = close_method()
            if isawaitable(result):
                await result
        self._active_stream = None
        await self._emit_observation("shutdown_completed")

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

        self._stop_requested = False
        checkpoint_store = self._checkpoint_store
        stream_key = self._checkpoint_key_builder(request)
        if checkpoint_store is not None and request.replay_id is None:
            stored_replay_id = checkpoint_store.load(stream_key)
            if stored_replay_id is not None:
                request = request.model_copy(update={"replay_id": stored_replay_id})

        metadata = await self._resolve_metadata()
        await self._emit_observation(
            "subscribe_started",
            channel=request.channel,
            replay_id=request.replay_id,
        )
        stream = self._subscribe_with_reconnect(request, metadata)
        if checkpoint_store is None:
            self._active_stream = stream
            return stream
        wrapped_stream = _CheckpointingCDCStream(
            stream,
            checkpoint_store=checkpoint_store,
            stream_key=stream_key,
            on_checkpoint_saved=self._observe_checkpoint_saved,
        )
        self._active_stream = wrapped_stream
        return wrapped_stream

    async def _subscribe_with_reconnect(
        self,
        request: SalesforceCDCSubscribeRequest,
        metadata: dict[str, str],
    ) -> AsyncIterator[SalesforceCDCEvent]:
        """Subscribe with bounded reconnect using the latest replay cursor.

        A reconnect attempt resumes from the last delivered event, never past
        unprocessed events in a partially consumed response. If the stream
        breaks before any cursor is known, the subscriber fails clearly
        because a safe resume point does not exist yet.
        """
        pubsub = self._pubsub
        if pubsub is None:
            return

        replay_id = request.replay_id
        attempts = 0

        while True:
            if self._stop_requested:
                await self._emit_observation("stream_stopped", reason="shutdown")
                self._active_stream = None
                return
            resumed_request = request.model_copy(update={"replay_id": replay_id})
            requests = _FetchRequestStream(resumed_request)
            self._active_requests = requests
            stream = None
            self._reading = True
            try:
                stream = await pubsub.subscribe(
                    requests,
                    metadata=metadata,
                )
                self._active_response_stream = stream
                # Each reconnect replays the same orchestration path: subscribe,
                # decode envelopes, update the latest replay cursor, and yield
                # typed CDC events downstream.
                async for event in self._event_stream(
                    stream,
                    metadata,
                    requests,
                ):
                    replay_id = event.replay_id
                    attempts = 0
                    self._reading = False
                    yield event
                    self._reading = True
                return
            except asyncio.CancelledError:
                if not self._stop_requested:
                    raise
                return
            except (GrpcStatusError, GrpcTransportError) as exc:
                attempts = await self._handle_reconnectable_error(
                    exc, replay_id=replay_id, attempts=attempts
                )
            except Exception as exc:
                attempts = await self._handle_native_grpc_error(
                    exc, replay_id=replay_id, attempts=attempts
                )
            finally:
                await requests.aclose()
                await self._close_stream(stream)
                self._active_requests = None
                self._active_response_stream = None
                self._reading = False

    @staticmethod
    async def _close_stream(value: Any) -> None:
        """Close a subscriber-owned stream with synchronous or async cleanup"""
        close = _resolve_close_method(value)
        if close is not None:
            result = close()
            if isawaitable(result):
                await result

    async def _handle_native_grpc_error(
        self, exc: Exception, *, replay_id: int | None, attempts: int
    ) -> int:
        """Classify native RPC errors without retrying unrelated failures"""
        mapped = self._map_native_grpc_error(exc)
        if mapped is None:
            raise exc
        if isinstance(mapped, GrpcStatusError) and mapped.status_code == 3:
            raise SalesforceCDCReplayInvalidError(
                "Salesforce rejected the replay cursor as invalid or "
                "outside the 72-hour retention window; resubscribe "
                "with EARLIEST or trigger a full reconciliation "
                f"(replay_id={replay_id!r})"
            ) from mapped
        return await self._handle_reconnectable_error(
            mapped, replay_id=replay_id, attempts=attempts
        )

    async def _handle_reconnectable_error(
        self,
        exc: Exception,
        *,
        replay_id: int | None,
        attempts: int,
    ) -> int:
        """Apply the bounded-reconnect policy and return the updated attempt count."""
        if replay_id is None:
            raise RuntimeError(
                "Salesforce CDC stream interrupted before a replay "
                "cursor was established"
            ) from exc
        if attempts >= self._reconnect_max_attempts:
            await self._emit_observation(
                "reconnect_exhausted",
                attempts=attempts,
                replay_id=replay_id,
            )
            raise RuntimeError("Salesforce CDC reconnect attempts exhausted") from exc
        attempts += 1
        await self._emit_observation(
            "reconnect_attempt",
            attempt=attempts,
            replay_id=replay_id,
        )
        return attempts

    @staticmethod
    def _map_native_grpc_error(
        exc: Exception,
    ) -> GrpcStatusError | GrpcTransportError | None:
        """Map a native grpc error to a plynth error, or None if not a grpc error.

        The generic ``plynth.grpc`` client already maps native errors for its
        own call paths. The vendored Pub/Sub stub bypasses that client and
        raises native ``grpc.RpcError`` directly, so this duck-types on the
        ``code``/``details`` shape grpc errors expose rather than importing
        ``grpc`` unconditionally (it remains an optional extra).
        """
        code_attr = getattr(exc, "code", None)
        if not callable(code_attr):
            return None
        mapped = GrpcAioTransport._map_error("Subscribe", exc)
        return cast("GrpcStatusError | GrpcTransportError", mapped)

    async def _event_stream(
        self,
        stream: AsyncIterator[Any],
        metadata: dict[str, str],
        requests: _FetchRequestStream,
    ) -> AsyncIterator[SalesforceCDCEvent]:
        """Yield typed CDC events from a raw Subscribe response stream"""
        async for response in stream:
            if self._stop_requested:
                await self._emit_observation("stream_stopped", reason="shutdown")
                return
            await self._raise_for_gap_or_overflow(response)
            latest_replay_id = self._extract_latest_replay_id(response)
            raw_events = self._extract_events(response)
            for raw_event in raw_events:
                if self._stop_requested:
                    return
                event = await self._to_cdc_event(
                    raw_event,
                    metadata=metadata,
                    latest_replay_id=latest_replay_id,
                )
                if event is not None:
                    yield event
            requests.processed(response, len(raw_events))

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
            await self._emit_observation("decode_skipped", reason="missing_payload")
            return None

        decoder = self._payload_decoder
        if decoder is None:
            await self._emit_observation("decode_skipped", reason="missing_decoder")
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
            changed_fields=self._field_bitmap_decoder.decode(
                schema_json, header.get("changedFields")
            ),
            nulled_fields=self._field_bitmap_decoder.decode(
                schema_json, header.get("nulledFields")
            ),
            diff_fields=self._field_bitmap_decoder.decode(
                schema_json, header.get("diffFields")
            ),
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
            await self._emit_observation("schema_cache_miss", schema_id=schema_id)
            self._schema_cache[schema_id] = await self._schema_loader(
                schema_id,
                metadata,
            )
        else:
            await self._emit_observation("schema_cache_hit", schema_id=schema_id)
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

    async def _raise_for_gap_or_overflow(self, response: Any) -> None:
        """Raise clear stream errors for normalized gap or overflow signals."""
        if not isinstance(response, dict):
            return

        latest_replay_id = AsyncSalesforceCDCSubscriber._coerce_optional_int(
            response.get("latest_replay_id")
        )
        detail = response.get("error_message")
        suffix = AsyncSalesforceCDCSubscriber._format_stream_error_suffix(
            latest_replay_id,
            detail,
        )

        if response.get("gap") is True:
            await self._emit_observation(
                "gap_detected",
                latest_replay_id=latest_replay_id,
                error_message=detail,
            )
            raise SalesforceCDCGapError(
                f"Salesforce CDC stream reported a replay gap{suffix}"
            )
        if response.get("overflow") is True:
            await self._emit_observation(
                "overflow_detected",
                latest_replay_id=latest_replay_id,
                error_message=detail,
            )
            raise SalesforceCDCOverflowError(
                f"Salesforce CDC stream reported an overflow event{suffix}"
            )

    @staticmethod
    def _format_stream_error_suffix(
        latest_replay_id: int | None,
        detail: Any,
    ) -> str:
        """Build a stable diagnostic suffix for normalized stream errors."""
        parts: list[str] = []
        if latest_replay_id is not None:
            parts.append(f"latest_replay_id={latest_replay_id}")
        if isinstance(detail, str) and detail:
            parts.append(detail)
        if not parts:
            return ""
        return f" ({'; '.join(parts)})"

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

    @staticmethod
    def _default_checkpoint_key(request: SalesforceCDCSubscribeRequest) -> str:
        """Build the default checkpoint key for one CDC subscription."""
        return request.channel

    async def _emit_observation(self, name: str, **details: Any) -> None:
        """Send one lightweight lifecycle observation to the optional hook."""
        observer = self._observer
        if observer is None:
            return
        result = observer(name, details)
        if isawaitable(result):
            await result

    def _observe_checkpoint_saved(self, replay_id: int) -> None:
        """Emit a synchronous checkpoint-saved observation."""
        observer = self._observer
        if observer is None:
            return
        observer("checkpoint_saved", {"replay_id": replay_id})
