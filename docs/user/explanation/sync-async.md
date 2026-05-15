# Sync and async in Plynth

Plynth supports both sync and async execution models without duplicating
business logic. This article explains how the models are separated and when
to choose each.

## The separation

Plynth separates execution model from business logic across three layers:

| Layer            | Sync                         | Async                                  |
| ---------------- | ---------------------------- | -------------------------------------- |
| **Transport**    | `HttpxSyncTransport`         | `HttpxAsyncTransport`                  |
| **Client**       | `HTTPClient` / `APIClient`   | `AsyncHTTPClient` / `AsyncAPIClient`   |
| **Service base** | `HTTPService` / `APIService` | `AsyncHTTPService` / `AsyncAPIService` |
| **Middleware**   | `SyncMiddleware` protocol    | `AsyncMiddleware` protocol             |

Your domain logic — building requests, parsing responses, mapping errors —
lives in the service layer and is the same regardless of execution model.
Only the transport and client classes differ.

## Why not a single universal client?

A single client that wraps both sync and async would require either
`asyncio.run()` wrappers (blocks in async contexts) or thread-pool
executors (added complexity and overhead). Instead, Plynth provides
dedicated classes so you pick the model that matches your stack — with no
adapters and no surprises.

## Choosing between sync and async

| Use sync when                              | Use async when                                     |
| ------------------------------------------ | -------------------------------------------------- |
| Script, CLI, or simple data pipeline       | Web server or async framework (FastAPI, Starlette) |
| Sequential operations only                 | Concurrent API calls with `asyncio.gather`         |
| Simplicity matters more than throughput    | Latency or concurrency matters                     |
| Synchronous framework (Django WSGI, Flask) | Django ASGI or any async context                   |

## Async parity

Every sync class has an async counterpart with identical behaviour and
identical method signatures. Any middleware, service, or connector that
exists in the sync variant also exists in the async variant.

When writing a connector for both models, create a sync service class and
an async service class that share the URL-building and response-parsing
logic via helper methods or module-level functions.

## Mixing sync and async

Do not call sync transport methods from inside an async context without a
thread pool — it will block the event loop. If you need to call a sync
library from async code, use `asyncio.to_thread()`:

```python
import asyncio
from plynth.http.transport import HttpxSyncTransport

transport = HttpxSyncTransport()

async def fetch():
    result = await asyncio.to_thread(transport.send, request)
    return result
```

For production async use, always use `HttpxAsyncTransport` and
`AsyncAPIClient` directly.
