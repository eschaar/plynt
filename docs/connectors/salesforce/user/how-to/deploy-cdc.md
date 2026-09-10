# How to deploy the Salesforce CDC subscriber in Kubernetes

The CDC subscriber is an at-least-once, long-lived stream consumer. It must
be deployed with a durable checkpoint backend and graceful shutdown handling
so pod restarts and rollouts do not lose or duplicate progress beyond what
at-least-once delivery already implies.

## Connecting to Salesforce Pub/Sub

Plynth vendors the generated Salesforce `eventbus.v1` Pub/Sub stub, so you
do not need to run `protoc` yourself. Build a gRPC channel and pass it to
`create_vendored_pubsub_adapter`:

```python
import grpc
from plynth.connectors.salesforce.cdc import (
    AsyncSalesforceCDCSubscriber,
    create_vendored_pubsub_adapter,
)

channel = grpc.aio.secure_channel(
    "api.pubsub.salesforce.com:7443", grpc.ssl_channel_credentials()
)
subscriber = AsyncSalesforceCDCSubscriber(
    pubsub=create_vendored_pubsub_adapter(channel),
    auth_metadata_provider=auth_metadata_provider,
    payload_decoder=avro_payload_decoder,
)
```

If you need a custom-generated stub instead (for example a different
Pub/Sub API version), construct `GrpcStubPubSubAdapter(your_stub)` directly.

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
  is for local development and tests only — plynth does not ship a
  production `CacheBackend` implementation, so provide one for your backend
  of choice.
- Add a startup check for production profiles that fails closed when no
  durable `CacheBackend` is configured, rather than silently falling back to
  `InMemorySalesforceCDCCheckpointStore`.

```python
from plynth.connectors.salesforce.cdc import AsyncSalesforceCDCSubscriber
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
    client=grpc_client,
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
