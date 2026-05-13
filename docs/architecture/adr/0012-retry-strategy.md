# ADR-0012: Retry Strategy

## Status

Accepted

## Implementation Notes

**Implemented:** `RetryPolicy` (`plynth.base.policies`), `HttpRetryPolicy`
(`plynth.http.policies`), `RetryMiddleware` / `AsyncRetryMiddleware`
(`plynth.middleware.retry`), wiring via
`HttpxSyncTransport.from_settings()`, and the typed `retry` property on
`HTTPSettings` (see "Typed retry configuration via settings" below).

**Superseded:** `RetryingSyncTransport` / `RetryingAsyncTransport` standalone
wrapper classes (original proposal) — replaced by the `retry_policy=` argument
on `BaseSyncTransport` (ADR-0013).

## Context

Transient failures are common when integrating with external APIs:
connection resets, gateway timeouts (`502`, `503`, `504`), and rate-limiting
responses (`429`) can all occur during normal operation. A client library
without built-in retry support forces every consumer to implement retries
independently, leading to inconsistent behaviour and duplicated logic.

Retries must:

- Be **opt-in** — never enabled silently.
- Apply at the **transport layer** — below clients and services, so they are
  invisible to callers (ADR-0008 explicitly excludes retry from the client).
- Support **backoff** — repeating immediately is rarely correct.
- Distinguish **retryable** from **non-retryable** failures — `400 Bad Request`
  must never be retried.

## Decision

### Retry lives in `BaseSyncTransport`

Retry logic is implemented once in `BaseSyncTransport._send_with_retry()` and
inherited by all concrete transport implementations. See ADR-0013 for the full
design. No separate `RetryingSyncTransport` wrapper class is introduced.

### `RetryPolicy` / `HttpRetryPolicy` data classes

`RetryPolicy` is protocol-agnostic and lives in `plynth.base.policies`:

```python
from dataclasses import dataclass, field

@dataclass
class RetryPolicy:
    max_attempts: int = 3
    backoff_initial: float = 0.5
    backoff_multiplier: float = 2.0
    backoff_max: float = 30.0
    retry_on_network_error: bool = True
    # Empty by default — non-HTTP transports have no retryable status codes.
    retryable_status_codes: frozenset[int] = field(default_factory=frozenset)
```

`HttpRetryPolicy` (`plynth.http.policies`) extends `RetryPolicy` with HTTP
defaults:

```python
@dataclass
class HttpRetryPolicy(RetryPolicy):
    # Defaults to {429, 500, 502, 503, 504}.
    retryable_status_codes: frozenset[int] = field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504})
    )
```

Pass `HttpRetryPolicy` to `HttpxSyncTransport` or `HttpxAsyncTransport`.
Use `RetryPolicy` for custom transports that are not HTTP-based.

Both are pure data carriers with no dependency on any HTTP library.

### `Policy` vs `Config` naming

`RetryPolicy` is intentionally named `*Policy`, not `*Config`.

- `*Config` dataclasses (e.g. `LocMemCacheConfig`, `RedisCacheConfig` from
  ADR-0010) answer the question *"which backend to instantiate and with
  what connection options?"*. They are construction-time descriptors.
- `RetryPolicy` answers the question *"how should the transport behave when
  a request fails?"*. It describes behavioral rules: backoff timing,
  retryable status codes, and attempt limits.

The distinction is meaningful and intentional. Do not rename `RetryPolicy`
to `RetryConfig`.

### `RetryingSyncTransport` / `RetryingAsyncTransport`

These standalone wrapper classes are **not implemented** (see Note above).
Retry logic lives in `BaseSyncTransport._send_with_retry()` instead.

### Backoff algorithm

Exponential backoff with a configurable ceiling:

```text
delay_n = min(backoff_initial × backoff_multiplier^n, backoff_max)
```

Jitter (randomisation) is deliberately excluded from the default policy to
keep behaviour predictable and deterministic in tests. Callers that need jitter
can subclass `RetryPolicy` or provide a custom transport.

### Retryable vs non-retryable status codes

Default `HttpRetryPolicy` retryable codes: `{429, 500, 502, 503, 504}`.

- `4xx` (except `429`) are **not** retried — they indicate caller errors.
- `401` triggers reactive re-auth in `BaseSyncTransport` (outside the retry
  loop), not an additional retry — see ADR-0013 and ADR-0011.
- `3xx` redirects are not retried — they are transport-level concerns.

### Composition order

The canonical execution order inside `BaseSyncTransport.send()` is:

```text
Cache check → Attach auth → Retry loop → _send_once()
    → Reactive auth (401) → Cache store
```

See ADR-0013 for the full design. There is no manual wrapper nesting.

### Retry settings

`HTTPSettings` exposes a single retry field:

```text
PLYNTH_MAX_ATTEMPTS=3
```

`HttpxSyncTransport.from_settings()` reads `settings.max_attempts` and
constructs an `HttpRetryPolicy(max_attempts=settings.max_attempts)`. Backoff
parameters use the `HttpRetryPolicy` defaults and are not currently
configurable via settings.

### Typed retry configuration via settings

`HTTPSettings` exposes a `retry` property that returns an `HttpRetryPolicy | None`.
Override it in a subclass to expose the full set of backoff parameters
to the settings layer without using the flat `max_attempts` field:

```python
from plynth.http.policies import HttpRetryPolicy
from plynth.http.settings import HTTPSettings

class MySettings(HTTPSettings):
    @property
    def retry(self) -> HttpRetryPolicy:
        return HttpRetryPolicy(
            max_attempts=5,
            backoff_initial=1.0,
            retryable_status_codes=frozenset({429, 503}),
        )
```

`HttpxSyncTransport.from_settings()` and `HttpxAsyncTransport.from_settings()`
prefer `settings.retry` when it returns a non-`None` value. When it returns
`None` (the default), they fall back to
`HttpRetryPolicy(max_attempts=settings.max_attempts)`.

**Note:** The property returns `HttpRetryPolicy` directly, not a separate
`RetryConfig` wrapper class. This avoids introducing a redundant indirection
given that `HttpRetryPolicy` is already a plain data class with no behaviour.
See the "`Policy` vs `Config` naming" section below for the rationale.

### Scope boundaries

| Concern                          | Location                             |
| -------------------------------- | ------------------------------------ |
| `RetryPolicy` dataclass          | `plynth.base.policies`               |
| `HttpRetryPolicy` dataclass      | `plynth.http.policies`               |
| `RetryingSyncTransport`          | superseded — see ADR-0013            |
| `RetryingAsyncTransport`         | superseded — see ADR-0013            |
| `max_attempts` field in settings | `plynth.http.settings`               |
| `retry` typed property           | `plynth.http.settings.HTTPSettings`  |
| Retry wiring from settings       | `HttpxSyncTransport.from_settings()` |

No retry logic is placed in clients, services, or the `core.base` abstractions.

## Consequences

- Retry is fully opt-in and composable with auth and caching.
- `RetryPolicy` can be passed by value, stored, copied, and tested without
  any network involvement.
- The default backoff avoids hammering a struggling server.
- Non-retryable failures are surfaced immediately without delay.
- Test code can set `max_attempts=1` and `retry_on_network_error=False` to
  disable retries entirely.

## Related

- ADR-0003 — Dependency Policy
- ADR-0006 — Transport Layer
- ADR-0008 — Client Layer
- ADR-0010 — Optional Caching Extra
- ADR-0004 — Settings and Configuration
- ADR-0011 — Authentication
