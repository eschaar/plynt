# ADR-0004: Settings and Configuration

## Status

Accepted

## Implementation Notes

**Partly superseded:** A `TransportConfig` dataclass and `transport_config()`
factory were proposed in an earlier draft. Neither was implemented. Transport
fields (`proxy`, `verify`, `cert`, and the four timeout fields) live directly
on `HTTPSettings` instead.

## Context

A robust, framework-agnostic, and testable configuration system is essential for
a reusable API client library. Configuration must be explicit, typed,
environment-driven, and extensible, without introducing global state or
framework lock-in.

The transport level needs additional fields for proxy settings, TLS options, and
per-phase timeouts. These belong alongside the HTTP settings rather than in a
separate `TransportConfig` object, so the environment-variable surface area is
unified.

## Decision

### Core Principles

- **Framework-agnostic**: no dependency on Django, FastAPI, or any framework.
- **Typed & validated**: all settings are typed and validated at instantiation.
- **Environment-first**: config is loaded from environment variables (with
  optional `.env` file support).
- **Explicit injection**: settings are always passed explicitly to clients and
  services, never imported as globals.
- **Extensible via subclassing**: users extend settings classes per service;
  framework adapters live in optional extras only.
- **No globals/singletons**: no implicit or global settings; always explicit
  and testable.

### Three-Layer Settings Structure

Settings are split across three layers:

**Layer 1 — Core base** (`plynt.base.settings.Settings`):

- Minimal `BaseSettings` subclass.
- Provides `.env` file support and UTF-8 encoding.
- Defines only `debug: bool = False`.
- All service settings must inherit from this class.

**Layer 2 — HTTP transport** (`plynt.http.settings.HTTPSettings`):

- Extends `Settings` with all fields needed to build and configure an
  `HttpxSyncTransport` or `HttpxAsyncTransport`.

*Connection and timeout fields:*

- `base_url: str` — base URL of the external service.
- `timeout_connect: float | None = 5.0` — connection timeout in seconds;
  `None` disables this phase timeout.
- `timeout_read: float | None = 30.0` — read timeout in seconds;
  `None` disables this phase timeout.
- `timeout_write: float | None = 10.0` — write timeout in seconds;
  `None` disables this phase timeout.
- `timeout_pool: float | None = 10.0` — connection-pool acquisition timeout
  in seconds; `None` disables this phase timeout.

*Retry:*

- `max_attempts: int = 3` — total send attempts including the first.

*TLS and proxy:*

- `proxy: str | None` — optional proxy URL.
- `verify: bool | str = True` — SSL certificate verification; `True` uses the
  system CA bundle, `False` disables verification, a string is a path to a
  custom CA bundle.
- `cert: tuple[str, str] | str | None` — optional client certificate;
  a `(cert, key)` tuple or path to a PKCS12 file.

*Auth:*

The flat credential fields (`bearer_token`, `client_id`, etc.) have been
removed. Service subclasses declare their own credential fields (pydantic
env-var fields) and return a typed `AuthConfig` object from the `auth`
property. See ADR-0011.

*Caching:*

Response and token caches are configured via typed `CacheConfig` objects
returned from the `caches`, `default_cache`, and `default_auth_cache`
properties. See ADR-0010.

**Layer 3 — REST API** (`plynt.http.settings.ApiSettings`):

- Extends `HTTPSettings` with no additional fields at present.
- Reserved for future REST-specific settings (e.g. content negotiation).
- Subclass this when building a JSON REST API client to remain
  forward-compatible with fields added in a future release.

### Implementation: pydantic-settings (Pydantic v2)

Use `pydantic-settings` as the only settings dependency in the core.

```python
from plynt.http.settings import ApiSettings
from plynt.http.transport import HttpxSyncTransport
from pydantic_settings import SettingsConfigDict


class CustomerServiceSettings(ApiSettings):
    model_config = SettingsConfigDict(
        env_prefix="CUSTOMER_",
        env_file=".env",
    )


settings = CustomerServiceSettings()
transport = HttpxSyncTransport.from_settings(settings)
client = APIClient(base_url=settings.base_url, transport=transport)
```

### Transport-Level Configuration Fields

The four timeout fields map to the corresponding phases of an `httpx2.Timeout`
object. Setting any field to `None` disables that phase's timeout. Each phase
can be tuned independently.

```text
PLYNT_PROXY=http://proxy.corp:8080
PLYNT_VERIFY=/etc/ssl/certs/ca-bundle.crt
PLYNT_TIMEOUT_CONNECT=5.0
PLYNT_TIMEOUT_READ=30.0
PLYNT_TIMEOUT_WRITE=10.0
PLYNT_TIMEOUT_POOL=10.0
```

The cert field (`PLYNT_CERT`) accepts a path or a `(cert, key)` tuple.

Transport configuration is wired inside each transport's `from_settings()`
factory. `HTTPSettings` must **not** grow transport-aware methods
(e.g. no `to_httpx_timeout()` or `to_requests_timeout()`). That logic belongs
inside each transport's `from_settings()`.

### Timeout Compatibility Across Transports

`HTTPSettings` defines four timeout phases that map directly to
`httpx2.Timeout`. Not every HTTP library supports all four phases. The contract
is: `HTTPSettings` is the **authoritative, transport-agnostic** model — it
does not shrink to the lowest common denominator. Each transport maps what
it can use and documents which fields it ignores.

| Field             | httpx2                        | requests          |
| ----------------- | ----------------------------- | ----------------- |
| `timeout_connect` | `httpx2.Timeout(connect=...)` | `timeout[0]`      |
| `timeout_read`    | `httpx2.Timeout(read=...)`    | `timeout[1]`      |
| `timeout_write`   | `httpx2.Timeout(write=...)`   | *(not supported)* |
| `timeout_pool`    | `httpx2.Timeout(pool=...)`    | *(not supported)* |

### Framework Adapters (Extras Only)

- **Django**: subclass `ApiSettings` in the `[django]` extra only.
- **FastAPI**: wrap with `lru_cache` and expose via `Depends(get_settings)` in
  the `[fastapi]` extra only.
- No framework-specific logic is allowed in the core.

### What Does Not Belong in Settings

- ❌ Cache instances (`LocMemCache`, `RedisCache`, …)
- ❌ Runtime state
- ❌ Client or transport instances

These belong in cache backends or client objects.

Cache configuration is expressed via typed `CacheConfig` objects returned from
the `caches` property. The URL/location (a secret) is a separate pydantic
env-var field on the subclass. See ADR-0010 for the full typed cache config
pattern.

Auth credentials are not flat fields on `HTTPSettings`; they are pydantic
env-var fields on the service subclass, assembled into an `AuthConfig` object
in the `auth` property. See ADR-0011 for the full typed auth config pattern.

### Best Practices

- Subclass `ApiSettings` per service with a unique `env_prefix`.
- All config via environment variables; `.env` for local development.
- No branching on frameworks in the core.
- Settings are immutable config, not runtime state.

## Alternatives Considered

### msgspec + msgspec-ext

[msgspec](https://jcristharif.com/msgspec/) is a high-performance serialization
and validation library. [msgspec-ext](https://github.com/msgflux/msgspec-ext)
extends it with a `BaseSettings` implementation and 26 built-in validators,
positioning itself as a drop-in replacement for pydantic-settings (7× faster
cold start, 169× faster warm/cached loads).

**Why not chosen:**

1. **Performance advantage is real but irrelevant for this use case.**
   Plynt is an HTTP integration library. Every request involves network I/O
   that dominates total latency by two to three orders of magnitude:

   ```text
   DNS + TCP connect:              10–30 ms
   TLS handshake:                   5–15 ms
   Remote server processing:       50–200 ms
   ────────────────────────────────────────
   Total I/O:                      65–245 ms

   pydantic-settings cold start:    ~2.5 ms   (once, at process startup)
   msgspec-ext cold start:          ~0.35 ms
   Absolute saving:                 ~2.1 ms   (unmeasurable in production)
   ```

1. **Framework adapter compatibility.** FastAPI is built on pydantic natively.
   A `plynt[fastapi]` adapter on msgspec structs would create a permanent
   impedance mismatch — connector response models would need conversion to
   pydantic models for OpenAPI schema generation and request/response binding.
   Django REST Framework has established pydantic integration tooling; msgspec
   has none.

1. **msgspec-ext maturity risk.** At the time of evaluation (May 2026),
   msgspec-ext had 12 GitHub stars, 4 forks, 4 releases, and approximately
   10 months of history. It had no documented production deployments at scale.
   For a library dependency that ships to downstream users this level of
   immaturity is not acceptable.

1. **MessagePack is unused in the target API domain.** All APIs Plynt
   targets (Salesforce REST, OpenAI/LLM APIs, REST APIs in general) use JSON
   as their wire format. gRPC uses Protocol Buffers, not MessagePack.
   msgspec's MessagePack support provides no benefit in this context.

1. **Connector model primitives have no msgspec equivalent.**
   `PrivateAttr`, `RootModel`, and `TypeAdapter` patterns used in connector
   schemas require bespoke workarounds in msgspec.

If performance profiling ever identifies pydantic validation as a real
bottleneck — which is only plausible for offline bulk processing paths, not
for the HTTP integration use case — revisit this decision with measured data.

## Consequences

- Configuration is explicit, testable, and framework-agnostic.
- Each service has its own isolated settings with no env-var collisions.
- No global state or hidden dependencies.
- The library is easy to use in any context: scripts, CLI, Django, FastAPI,
  and unit tests.
- Adding a new transport library (e.g. `aiohttp`) only requires reading the
  relevant `HTTPSettings` fields in its own `from_settings()`.
- Transport authors must document which timeout fields they consume and which
  they ignore, in the `from_settings()` docstring.

## Related

- ADR-0003 — Dependency Policy (optional extras model)
- ADR-0006 — Transport Layer
- ADR-0010 — Caching
- ADR-0011 — Authentication
- ADR-0012 — Retry Strategy
