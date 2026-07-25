# How to build a FastAPI facade with Plynth

Use FastAPI for your inbound API contract and plynth for outbound backend
calls. This pattern is a strong fit for integration services that expose a
stable service API while orchestrating one or more external systems.

Typical examples:

1. A facade API in front of a CRM or support SaaS backend.
1. A workflow API that combines multiple SaaS and internal platform backends.
1. A composite integration endpoint that merges data from two upstream APIs.

## Install extras

Install FastAPI support plus the transport and connector extras you need.

```bash
pip install "plynth[fastapi,httpx]"
```

Add connector-specific extras only when you need connector-specific services.

## Define typed settings per upstream

Use one `HTTPSettings` subclass per upstream backend. This keeps auth and retry
policy explicit and testable.

```python
from pydantic_settings import SettingsConfigDict

from plynth.http.auth import OAuth2ClientCredentialsConfig
from plynth.http.settings import HTTPSettings


class SaaSBackendASettings(HTTPSettings):
    model_config = SettingsConfigDict(env_prefix="BACKEND_A_", env_file=".env")

    client_id: str = ""
    client_secret: str = ""
    token_url: str = ""

    @property
    def auth(self) -> OAuth2ClientCredentialsConfig | None:
        if not self.client_id or not self.client_secret or not self.token_url:
            return None
        return OAuth2ClientCredentialsConfig(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_url=self.token_url,
        )


class SaaSBackendBSettings(HTTPSettings):
    model_config = SettingsConfigDict(env_prefix="BACKEND_B_", env_file=".env")
```

## Register named transports with `PlynthLifespan`

Create one named transport per upstream and let FastAPI own the lifecycle.

```python
from fastapi import FastAPI

from plynth.adapters.fastapi import PlynthLifespan
from plynth.http.transport import HttpxAsyncTransport


def build_backend_a_transport() -> HttpxAsyncTransport:
    return HttpxAsyncTransport.from_settings(SaaSBackendASettings())


def build_backend_b_transport() -> HttpxAsyncTransport:
    return HttpxAsyncTransport.from_settings(SaaSBackendBSettings())


app = FastAPI(
    lifespan=PlynthLifespan(
        {
            "backend_a": build_backend_a_transport,
            "backend_b": build_backend_b_transport,
        }
    )
)
```

`PlynthLifespan` closes resources using `aclose()` or `close()`, so both async
and sync transport objects can be managed safely.

## Resolve outbound dependencies with `Depends`

Use `get_transport(name)` when you want full control over client or service
construction.

```python
from fastapi import Depends

from plynth.adapters.fastapi import get_transport
from plynth.http.client import AsyncAPIClient


@app.get("/tickets")
async def list_tickets(
    backend_b_transport=Depends(get_transport("backend_b")),
):
    client = AsyncAPIClient(
        base_url="https://api.backend-b.example",
        transport=backend_b_transport,
    )
    response = await client.get("/items")
    response.raise_for_status()
    return response.json()
```

Use `get_client(...)` when the client constructor matches a `transport=`
keyword and you only need lightweight dependency wiring.

```python
from fastapi import Depends

from plynth.adapters.fastapi import get_client
from plynth.http.client import AsyncAPIClient


@app.get("/products")
async def list_products(
    backend_a_client: AsyncAPIClient = Depends(
        get_client(
            "backend_a",
            AsyncAPIClient,
            base_url="https://api.backend-a.example",
        )
    ),
):
    response = await backend_a_client.get("/products")
    response.raise_for_status()
    return response.json()
```

Use `get_service(...)` when you want one named service factory with optional
request-level caching.

```python
from fastapi import Depends

from plynth.adapters.fastapi import get_service
from plynth.http.client import AsyncAPIClient


def build_orders_service(transport: object) -> AsyncAPIClient:
    return AsyncAPIClient(
        base_url="https://api.backend-a.example",
        transport=transport,
    )


@app.get("/orders")
async def list_orders(
    orders_service: AsyncAPIClient = Depends(
        get_service(
            "orders_service",
            transport_name="backend_a",
            factory=build_orders_service,
        )
    ),
):
    response = await orders_service.get("/orders")
    response.raise_for_status()
    return response.json()
```

Use `build_service_dependencies(...)` when one router needs multiple service
dependencies on the same transport.

```python
from fastapi import APIRouter, Depends

from plynth.adapters.fastapi import build_service_dependencies
from plynth.http.client import AsyncAPIClient

router = APIRouter(prefix="/orders")


def build_orders_service(transport: object) -> AsyncAPIClient:
    return AsyncAPIClient(
        base_url="https://api.backend-a.example",
        transport=transport,
    )


def build_tickets_service(transport: object) -> AsyncAPIClient:
    return AsyncAPIClient(
        base_url="https://api.backend-b.example",
        transport=transport,
    )


service_deps = build_service_dependencies(
    transport_name="backend_a",
    factories={
        "orders_service": build_orders_service,
        "tickets_service": build_tickets_service,
    },
)


@router.get("/{order_id}")
async def get_order_view(
    order_id: str,
    orders_service: AsyncAPIClient = Depends(service_deps["orders_service"]),
    tickets_service: AsyncAPIClient = Depends(service_deps["tickets_service"]),
):
    order_resp = await orders_service.get(f"/orders/{order_id}")
    order_resp.raise_for_status()
    ticket_resp = await tickets_service.get("/tickets", params={"order_id": order_id})
    ticket_resp.raise_for_status()
    return {"order": order_resp.json(), "tickets": ticket_resp.json()}
```

## Propagate selected inbound headers

Use header helpers to forward correlation and trace headers from inbound
FastAPI requests into outbound plynth calls.

```python
from fastapi import Depends, Request

from plynth.adapters.fastapi import build_async_request_header_middleware
from plynth.http.client import AsyncAPIClient
from plynth.http.transport import HttpxAsyncTransport


def build_scoped_client(request: Request, transport: HttpxAsyncTransport) -> AsyncAPIClient:
    header_mw = build_async_request_header_middleware(request)
    scoped_transport = HttpxAsyncTransport(
        client=transport._client,  # share existing httpx client
        middlewares=[header_mw, *transport._middlewares],
    )
    return AsyncAPIClient(base_url="https://api.backend-a.example", transport=scoped_transport)
```

Use an explicit denylist when required:

```python
header_mw = build_async_request_header_middleware(
    request,
    headers={"X-Request-Id": "X-Request-Id", "traceparent": "traceparent"},
    deny_headers={"authorization", "cookie"},
)
```

## Map plynth exceptions to FastAPI JSON responses

Install plynth exception handlers once during app setup.

```python
from fastapi import FastAPI

from plynth.adapters.fastapi import install_plynth_exception_handlers


app = FastAPI(lifespan=...)
install_plynth_exception_handlers(app, include_details=False)
```

This maps:

1. `HttpStatusError` to its HTTP status code.
1. plynth `BaseError` subclasses to stable API status codes.
1. all mapped errors to safe JSON payloads with `message` and `code`.

## Build one orchestration endpoint over multiple backends

Use multiple named transports when one route combines upstream calls.

```python
from fastapi import Depends

from plynth.adapters.fastapi import get_transport
from plynth.http.client import AsyncAPIClient


@app.get("/orders/{order_id}")
async def get_order_view(
    order_id: str,
    backend_a_transport=Depends(get_transport("backend_a")),
    backend_b_transport=Depends(get_transport("backend_b")),
):
    backend_a = AsyncAPIClient(
        base_url="https://api.backend-a.example",
        transport=backend_a_transport,
    )
    backend_b = AsyncAPIClient(
        base_url="https://api.backend-b.example",
        transport=backend_b_transport,
    )

    order_resp = await backend_a.get(f"/orders/{order_id}")
    order_resp.raise_for_status()

    ticket_resp = await backend_b.get(
        "/tickets",
        params={"order_id": order_id},
    )
    ticket_resp.raise_for_status()

    return {
        "order": order_resp.json(),
        "tickets": ticket_resp.json(),
    }
```

This keeps FastAPI responsible for inbound HTTP behavior while plynth handles
outbound transport and middleware semantics.

If you use a connector-specific facade, apply the
same wiring pattern and swap `AsyncAPIClient` for the connector facade layer.

## Sync and async guidance

FastAPI supports both sync and async route handlers. Choose the matching
plynth client type:

1. Async route handlers (`async def`) should use async transports and clients.
1. Sync route handlers (`def`) should use sync transports and clients.
1. Avoid sync clients inside async handlers unless you explicitly offload to a
   worker thread.

### Async route example

```python
from fastapi import Depends

from plynth.adapters.fastapi import get_client
from plynth.http.client import AsyncAPIClient


@app.get("/accounts")
async def list_accounts(
    client: AsyncAPIClient = Depends(
        get_client(
            "backend_a",
            AsyncAPIClient,
            base_url="https://api.backend-a.example",
        )
    ),
):
    response = await client.get("/accounts")
    response.raise_for_status()
    return response.json()
```

### Sync route example

```python
from fastapi import Depends

from plynth.adapters.fastapi import get_client
from plynth.http.client import SyncAPIClient


@app.get("/health/upstream")
def upstream_health(
    client: SyncAPIClient = Depends(
        get_client(
            "backend_a",
            SyncAPIClient,
            base_url="https://api.backend-a.example",
        )
    ),
):
    response = client.get("/health")
    response.raise_for_status()
    return response.json()
```

## Framework capability matrix

Use this matrix as the current support boundary for framework adapters.

| Adapter          | Lifecycle helpers | Transport/client DI | Service DI helpers | Header propagation | Error mapping | Sync | Async |
| ---------------- | ----------------- | ------------------- | ------------------ | ------------------ | ------------- | ---- | ----- |
| Django core      | N/A               | N/A                 | N/A                | N/A                | N/A           | Yes  | Yes   |
| Django DRF layer | Request lifecycle | Yes                 | Yes                | Yes                | Yes           | Yes  | Yes   |
| FastAPI adapter  | Lifespan          | Yes                 | Yes                | Yes                | Yes           | Yes  | Yes   |

## Recommended facade boundaries

For SaaS-backend facade services:

1. Keep plynth settings, clients, and service factories in one module.
1. Keep route handlers thin: validate input, call orchestration service,
   return mapped response.
1. Keep business mapping logic outside route functions for testability.
1. Keep retries, timeouts, and auth policy in typed settings rather than in
   route code.
