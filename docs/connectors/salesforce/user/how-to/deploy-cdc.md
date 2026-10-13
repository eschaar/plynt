# How to deploy the Salesforce CDC subscriber in Kubernetes

The CDC subscriber is an at-least-once, long-lived stream consumer. It must
be deployed with a durable checkpoint backend and graceful shutdown handling
so pod restarts and rollouts do not lose or duplicate progress beyond what
at-least-once delivery already implies.

## Connecting to Salesforce Pub/Sub

Install the protocol and connector extras together:

```bash
pip install "plynth[grpc,salesforce]"
```

This includes the real Avro decoder. CDC is experimental: authenticate,
decode real schemas, and verify replay behavior against a Salesforce org
before using this deployment guidance in production.

Plynth vendors the generated Salesforce `eventbus.v1` Pub/Sub stub, so you
do not need to run `protoc` yourself. Build a gRPC channel and pass it to
`create_vendored_pubsub_adapter`:

```python
import grpc
from plynth.connectors.salesforce.cdc import (
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

CDC only delivers **changes from the moment you subscribe**. Building a
shadow database also requires a strategy for the initial snapshot and for
recovering from gaps larger than Salesforce's retention window. This is
inherently application-specific — plynth only guarantees clear, typed
signals; the recovery strategy itself is your application's responsibility.

### Initial load

1. Start the CDC subscription first (or at least note the `latest_replay_id`
   from the first keepalive `FetchResponse`) before running any bulk load.
   This fixes your resume point before the snapshot begins.
1. Perform the initial snapshot with the Salesforce Bulk API or SOQL
   (`plynth.connectors.salesforce`, not the CDC module — CDC has no
   "give me everything" mode).
1. Write the snapshot to your shadow database, then replay CDC events from
   the replay position captured in step 1, using **upsert by record ID**.
   Because delivery is at-least-once, some records may already be current
   from the snapshot; upsert makes that safe and idempotent.

### Gap recovery

Salesforce retains platform and CDC events for **72 hours**. There is no
"gap" flag in a normal `FetchResponse` — instead, resuming from a `replay_id`
outside the retention window (or otherwise invalid) fails the `Subscribe`
call itself with a gRPC `INVALID_ARGUMENT` status
(`sfdc.platform.eventbus.grpc.subscription.fetch.replayid.corrupted`).
`AsyncSalesforceCDCSubscriber` raises this as
`plynth.connectors.salesforce.cdc.SalesforceCDCReplayInvalidError` — a
non-retryable error, since resuming from the same cursor will fail
identically every time.

When you catch `SalesforceCDCReplayInvalidError`, choose one of:

- **Resubscribe with `replay_preset=EARLIEST`.** Only recovers events still
  inside the 72-hour window; anything older is already gone from the event
  bus itself and cannot be recovered from CDC at all.
- **Trigger a full reconciliation** of the affected object(s): re-run a
  SOQL/Bulk snapshot for those objects and upsert into the shadow database,
  the same way as the initial load. This is the only option once you are
  certain the gap exceeds 72 hours.

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
  satisfies `plynth.base.cache.CacheBackend`. `InMemorySalesforceCDCCheckpointStore`
  is for local development and tests only. Plynth's `RedisCache` can wrap
  an externally configured Redis client; install `redis` separately and
  configure persistence, authentication, and network isolation. The backend
  adapter alone does not guarantee checkpoint durability.
- Add a startup check for production profiles that fails closed when no
  durable `CacheBackend` is configured, rather than silently falling back to
  `InMemorySalesforceCDCCheckpointStore`.

```python
from plynth.connectors.salesforce.cdc import (
    AsyncSalesforceCDCSubscriber,
    AvroPayloadDecoder,
    create_vendored_pubsub_adapter,
)
from plynth.connectors.salesforce.cdc.checkpoint import (
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
