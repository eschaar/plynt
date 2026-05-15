# How to use async

Plynth provides async parity for every client, service, and middleware.
Async clients share the same service layer as their sync counterparts —
only the transport and top-level client differ.

## Build an async client

```python
import asyncio
from plynth.http.transport import HttpxAsyncTransport
from plynth.http.client import AsyncAPIClient
from plynth.http.auth import async_auth_from_config, OAuth2ClientCredentialsConfig

auth = async_auth_from_config(
    OAuth2ClientCredentialsConfig(
        client_id="my-client-id",
        client_secret="my-client-secret",
        token_url="https://auth.example.com/token",
    )
)
transport = HttpxAsyncTransport(middlewares=[auth])
client = AsyncAPIClient(base_url="https://api.example.com", transport=transport)
```

## Call async services

```python
async def main() -> None:
    response = await client.get("/items")
    print(response.json())

asyncio.run(main())
```

## Context manager for connection cleanup

Use the client as an async context manager to close the transport when done:

```python
async def main() -> None:
    async with AsyncAPIClient(
        base_url="https://api.example.com", transport=transport
    ) as client:
        response = await client.get("/items")
```

## Run multiple requests concurrently

Use `asyncio.gather` to send requests in parallel:

```python
import asyncio

async def main() -> None:
    items, users = await asyncio.gather(
        client.get("/items"),
        client.get("/users"),
    )
```

## Async service class

Subclass `AsyncAPIService` the same way as the sync variant:

```python
from plynth.http.service import AsyncAPIService
from dataclasses import dataclass


@dataclass
class Item:
    id: int
    name: str


class ItemService(AsyncAPIService):
    async def list(self) -> list[Item]:
        response = await self._client.get("/items")
        return [Item(**r) for r in response.json()]
```

## Async middleware

Use async variants for all middleware when using `HttpxAsyncTransport`:

```python
from plynth.middleware.logging import AsyncLoggingMiddleware
from plynth.middleware.retry import AsyncRetryMiddleware
from plynth.middleware.circuit_breaker import AsyncCircuitBreakerMiddleware
from plynth.middleware.cache import AsyncCacheMiddleware
from plynth.cache import LocMemCache
from plynth.http.policies import HttpRetryPolicy, HttpCircuitBreakerPolicy

transport = HttpxAsyncTransport(
    middlewares=[
        AsyncCacheMiddleware(LocMemCache(), ttl=120),
        AsyncLoggingMiddleware(),
        auth,
        AsyncRetryMiddleware(HttpRetryPolicy(max_attempts=3)),
        AsyncCircuitBreakerMiddleware(
            HttpCircuitBreakerPolicy(failure_threshold=5, recovery_timeout=30.0)
        ),
    ]
)
```

## Notes

- Async middleware classes use the same policy objects as sync ones.
- Do not mix sync and async services on the same transport instance.
- `pytest-asyncio` is recommended for testing async Plynth code.
