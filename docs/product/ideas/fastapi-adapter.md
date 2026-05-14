# Idea: FastAPI Adapter (`plynth[fastapi]`)

**Status:** Idea — not yet an ADR, no implementation started.

Convert to an ADR when the approach is agreed and implementation is about to
begin.

______________________________________________________________________

## Goal

Allow FastAPI applications to use plynth transports and clients with idiomatic
FastAPI patterns — specifically the lifespan context manager for resource
lifecycle and dependency injection (`Depends`) for per-request access.

FastAPI applications typically:

- manage long-lived resources (database connections, HTTP clients) via the
  `lifespan` parameter on the `FastAPI` app
- access shared resources in route handlers via `Depends()`
- are async-first — `httpx.AsyncClient` is the natural fit

The adapter removes the boilerplate of wiring these patterns manually so teams
can focus on their service code.

______________________________________________________________________

## Scope

### 1. Lifespan helper

`httpx.AsyncClient` must be created once and closed cleanly on shutdown.
Without an adapter, every team writes the same boilerplate:

```python
# without adapter — repeated in every project
@asynccontextmanager
async def lifespan(app: FastAPI):
    transport = HttpxAsyncTransport.from_settings(MyServiceSettings())
    app.state.transport = transport
    yield
    await transport.aclose()
```

The adapter provides a `PlynthLifespan` helper (or a factory function) that
handles this pattern generically for one or more named transports:

```python
from plynth.fastapi import PlynthLifespan
from myapp.settings import SalesforceSettings

lifespan = PlynthLifespan(salesforce=SalesforceSettings())

app = FastAPI(lifespan=lifespan)
```

Internally, `PlynthLifespan` creates and closes transports and stores them on
`app.state` under the given names.

Open question: should multiple transports be supported in one `PlynthLifespan`,
or should teams compose multiple lifespans using `anyio` task groups or a
third-party lifespan-composition library?

### 2. Dependency injection factory

Route handlers access the transport (or a client built from it) via `Depends`:

```python
from plynth.fastapi import get_transport

@app.get("/orders")
async def list_orders(
    transport: HttpxAsyncTransport = Depends(get_transport("salesforce")),
):
    client = AsyncAPIClient(base_url=settings.base_url, transport=transport)
    ...
```

`get_transport(name)` returns a `Depends`-compatible callable that reads the
named transport from `request.app.state`.

Higher-level helpers could inject a fully configured client directly:

```python
from plynth.fastapi import get_client

@app.get("/orders")
async def list_orders(client: AsyncAPIClient = Depends(get_client("salesforce"))):
    ...
```

### 3. Settings

FastAPI projects already use pydantic-settings — the same library plynth's
core uses. `HTTPSettings` subclasses work directly without a settings adapter.
What the `[fastapi]` extra adds is only the lifespan and DI utilities.

______________________________________________________________________

## Install extra

```text
pip install plynth[fastapi]
```

Adds `fastapi` as a dependency. The `[httpx]` extra is a prerequisite
(async transport requires httpx).

______________________________________________________________________

## Constraints

- No FastAPI imports anywhere in `plynth.core` or `plynth.http`.
- Must work with FastAPI 0.110+ (lifespan parameter stable since 0.93).
- Async-first — sync transport support in FastAPI is not a goal.
- The adapter must not force a specific project structure (e.g. where settings
  classes live).

______________________________________________________________________

## Open Questions

1. Single `PlynthLifespan` for multiple transports, or composable single-name
   helpers? The former is simpler; the latter is more flexible.
1. Does `get_transport()` / `get_client()` need to be a factory returning a
   `Depends`-compatible callable, or can it be a plain dependency function
   combined with a protocol?
1. Should the adapter provide a typed `PlynthState` class to make
   `request.app.state` type-safe, or is that too prescriptive?
1. Does the adapter ship as part of this repository or as a separate
   `plynth-fastapi` package from the start?

______________________________________________________________________

## Next Step

Write a new ADR covering the lifespan and DI design before any code is
written.
