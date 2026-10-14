# How to deploy the Salesforce CDC subscriber in Kubernetes

The CDC subscriber is an at-least-once, long-lived stream consumer. It must
be deployed with a durable checkpoint backend and graceful shutdown handling
so pod restarts and rollouts do not lose or duplicate progress beyond what
at-least-once delivery already implies.

## Connecting to Salesforce Pub/Sub

Install the protocol and connector extras together:

```bash
pip install "plynt[grpc,salesforce]"
```

This includes the real Avro decoder. CDC is experimental: authenticate,
decode real schemas, and verify replay behavior against a Salesforce org
before using this deployment guidance in production.

Plynt vendors the generated Salesforce `eventbus.v1` Pub/Sub stub, so you
do not need to run `protoc` yourself. Build a gRPC channel and pass it to
`create_vendored_pubsub_adapter`:

```python
import grpc
from plynt.connectors.salesforce.cdc import (
    AsyncSalesforceCDCSubscriber,
    AvroPayloadDecoder,
    create_vendored_pubsub_adapter,
)

channel = grpc.aio.secure_channel(
    "api.pubsub.salesforce.com:7443", grpc.ssl_channel_credentials()
)
subscriber = AsyncSalesforceCDCSubscriber(
    pubsub=create_vendored_pubsub_adapter(channel),
    auth_metadata_provider=auth_metadata_provider,
    payload_decoder=AvroPayloadDecoder(),
)
```

If you need a custom-generated stub instead (for example a different
Pub/Sub API version), construct `GrpcStubPubSubAdapter(your_stub)` directly.

## Flow control

`SalesforceCDCSubscribeRequest.num_requested` sets the batch size. The
subscriber keeps the bidirectional request stream open and requests another
batch only after the previous batch has been consumed. Asking for the next
event signals that the previous event has been processed; this also preserves
the existing deferred checkpoint behavior.

- Each request is capped at Salesforce's limit of 100 events.
- A batch can span multiple responses. `pending_num_requested` determines
  when the batch is complete; empty keepalives do not trigger additional
  requests while events are still pending.
- Custom adapters without `pending_num_requested` use delivered event
  counts instead. Skipped events still count against the requested batch.
- Reconnect starts a fresh request stream from the last delivered event,
  without skipping unprocessed events in a partially consumed response.
  Shutdown or consumer cancellation closes the request stream and cancels
  the upstream RPC.

Salesforce can close a stream if no new request arrives within 60 seconds
after the final response in a batch. Keep processing of that response below
this timeout; use a smaller batch when downstream processing is slow.

## Changed and nulled fields

`event.envelope.changed_fields`, `nulled_fields`, and `diff_fields` contain
decoded field names, not Salesforce's hexadecimal bitmap strings. The
subscriber resolves positions using the event's own cached Avro schema.
Compound fields use dotted names such as `BillingAddress.City`. Custom
payload decoders that already provide field names remain supported.

Malformed bitmaps or positions outside the schema raise an explicit error
instead of silently returning incorrect field names.

Pub/Sub payloads include unchanged fields with empty values. Do not overwrite
stored values merely because a payload field is `None`: use `changed_fields`
and `nulled_fields` to determine what changed. `diff_fields` identifies values
sent as diffs; applying those diffs remains the consumer's responsibility.

## Initial load and gap recovery

CDC delivers change events, not a full snapshot. The subscriber starts at
`LATEST` when no replay cursor is supplied or loaded from a checkpoint.
A supplied or stored `replay_id` selects `CUSTOM` for retained events.
`SalesforceCDCSubscribeRequest` does not expose a `replay_preset` field.
Building a shadow database also requires an initial snapshot and recovery
from gaps larger than Salesforce's retention window. These strategies are
application-specific; Plynt exposes typed events and errors, not an
atomic snapshot-and-stream handoff.

### Initial load

1. Start consuming before the snapshot and continuously persist events to
   an application-owned durable buffer. Wait until an event has been
   delivered and durably buffered before starting the snapshot; calling
   `subscribe` alone does not establish a provider-side boundary.
   Do not pause the subscription for a long bulk load: slow consumption
   can exceed the flow-control timeout.
1. Perform the initial snapshot with the Salesforce Bulk API or SOQL
   (`plynt.connectors.salesforce`, not the CDC module — CDC has no
   "give me everything" mode).
1. Reconcile the snapshot and buffered events using application-specific
   ordering and duplicate handling. Handle deletes as well as updates;
   blindly upserting older events can overwrite newer snapshot values.
   Verify the handoff against a real org and finish within the retention
   window, or perform a full reconciliation.

`await subscriber.subscribe(request)` returns an iterator; the upstream
subscription starts when that iterator is consumed. The subscriber does
not expose keepalive `FetchResponse.latest_replay_id` values or a provider
readiness signal. Do not use the subscribe call alone as proof that a safe
snapshot boundary exists. With checkpointing enabled, persist each event
before requesting the next one; the deferred checkpoint then represents
durable buffering, not completion of downstream reconciliation.

The public API currently uses integer replay IDs, while Salesforce treats
them as opaque bytes. Real-org cursor fidelity remains unverified; do not
assume the local gRPC tests prove a lossless initial-load or recovery path.

### Gap recovery

Salesforce retains platform and CDC events for **72 hours**. There is no
"gap" flag in a normal `FetchResponse` — instead, resuming from a `replay_id`
outside the retention window (or otherwise invalid) fails the `Subscribe`
call itself with a gRPC `INVALID_ARGUMENT` status
(`sfdc.platform.eventbus.grpc.subscription.fetch.replayid.corrupted`).
`AsyncSalesforceCDCSubscriber` raises this as
`plynt.connectors.salesforce.cdc.SalesforceCDCReplayInvalidError` — a
non-retryable error, since resuming from the same cursor will fail
identically every time.

When you catch `SalesforceCDCReplayInvalidError`, choose one of:

- **Resume from another known, valid cursor** if your application retains
  one within the 72-hour window. Ensure a stale checkpoint does not
  override the chosen recovery position.
- **Trigger a full reconciliation** of the affected object(s): re-run a
  SOQL/Bulk snapshot for those objects and upsert into the shadow database,
  the same way as the initial load. This is the only option once you are
  certain the gap exceeds 72 hours.

Salesforce's protocol also supports `EARLIEST`, but the current public
subscriber request cannot select it. Do not pass `replay_preset=EARLIEST`
to `SalesforceCDCSubscribeRequest`; it rejects unsupported fields.
An invalid stored checkpoint must be reset through your checkpoint backend
before starting a new subscription without an explicit replay cursor.

Do not treat `SalesforceCDCOverflowError` as a data-gap signal — Salesforce's
"overflow" error is a flow-control condition (too many events requested
before the previous batch was processed), unrelated to missed changes.

## Delivery and consumer expectations

- Treat the stream as **at-least-once delivery only**. Duplicate events are
  expected across reconnect, replay, and recovery paths.
- Make downstream consumers **idempotent** by `replay_id` (or an equivalent
  business key) before running this in production.
- Ordering is only preserved within a live subscription segment. After a
  reconnect or replay, do not assume gap-free global ordering.

## Checkpoint backend

- Use a **durable external checkpoint store** in Kubernetes:
  `CacheSalesforceCDCCheckpointStore` wrapping a `CacheBackend`
  implementation (Redis, memcached, or another external key-value store) that
  satisfies `plynt.base.cache.CacheBackend`. `InMemorySalesforceCDCCheckpointStore`
  is for local development and tests only. Plynt's `RedisCache` can wrap
  an externally configured Redis client; install `redis` separately and
  configure persistence, authentication, and network isolation. The backend
  adapter alone does not guarantee checkpoint durability.
- Add a startup check for production profiles that fails closed when no
  durable `CacheBackend` is configured, rather than silently falling back to
  `InMemorySalesforceCDCCheckpointStore`.

```python
from plynt.connectors.salesforce.cdc import (
    AsyncSalesforceCDCSubscriber,
    AvroPayloadDecoder,
    create_vendored_pubsub_adapter,
)
from plynt.connectors.salesforce.cdc.checkpoint import (
    CacheSalesforceCDCCheckpointStore,
)

if settings.environment == "production" and not settings.cache_backend:
    raise RuntimeError(
        "A durable CacheBackend is required in production; "
        "InMemorySalesforceCDCCheckpointStore is not production-safe."
    )

checkpoint_store = CacheSalesforceCDCCheckpointStore(
    backend=settings.cache_backend,  # e.g. a Redis-backed CacheBackend
)
subscriber = AsyncSalesforceCDCSubscriber(
    pubsub=create_vendored_pubsub_adapter(channel),
    auth_metadata_provider=auth_metadata_provider,
    payload_decoder=AvroPayloadDecoder(),
    checkpoint_store=checkpoint_store,
)
```

## Pod lifecycle and restarts

- Expect pod restarts, evictions, and rollout interruptions. The subscriber
  must resume from the last durable checkpoint rather than rely on process
  memory.
- Configure a `terminationGracePeriodSeconds` long enough for `SIGTERM` to
  reach the process and for `AsyncSalesforceCDCSubscriber.shutdown()` to stop
  intake and flush the last acknowledged checkpoint before the pod is killed.

```yaml
spec:
  terminationGracePeriodSeconds: 30
  containers:
    - name: cdc-subscriber
      # Send SIGTERM on scale-down/rollout; the process handles it via
      # shutdown() and exits once the last checkpoint is flushed.
```

```python
import asyncio
import signal


async def run() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop.set)

    consume_task = asyncio.create_task(consume(subscriber))
    await stop.wait()
    await subscriber.shutdown()
    await consume_task
```

## Consumer topology

- Do not run multiple active consumers against the same checkpointed stream
  unless you add external coordination (for example a leader-election lock).
  Without coordination, concurrent consumers on one stream duplicate work
  beyond the baseline at-least-once posture.

## Observability

Monitor these signals as baseline production indicators:

- Reconnect attempts and bounded-reconnect exhaustion.
- Replay gap and overflow signals — treat these as operator-visible
  incidents that may require a controlled reseed.
- Schema cache misses and decode skips.
- Checkpoint flush progress and lag relative to the live stream.
