# ADR-0014: Logging Strategy

## Status

Accepted

## Context

Plynt transports execute network I/O and cross-cutting operations (auth,
retry, caching) that are invisible to callers at runtime. Without structured
log output, operators cannot:

- observe retry storms or backoff intervals;
- correlate auth failures with upstream availability;
- tune log verbosity per logger (e.g. silence transport noise in tests);
- apply flood protection when an upstream becomes unavailable.

This ADR is the **single source of truth** for all logging decisions in
Plynt. It covers:

1. The `plynt.log` package (filters and formatter) and `plynt.middleware.logging`
   (HTTP middleware).
1. The logger hierarchy and which events are logged at which levels.
1. Opt-in body logging with mandatory credential scrubbing.

## Decision

### 1. Logger hierarchy

All loggers follow the `plynt.*` namespace so operators can target them
with a single handler configuration:

| Module                                                 | Logger name            |
| ------------------------------------------------------ | ---------------------- |
| `plynt.base.transport`                                 | `plynt.base.transport` |
| `plynt.http.transport`                                 | `plynt.http.transport` |
| `plynt.middleware.logging` (LoggingMiddleware default) | `plynt.http`           |

The root logger `plynt` is **not** used directly. Child loggers inherit
handler configuration from the `plynt` logger when operators set it up.

### 2. Log levels and events (always-on)

| Level     | Event                                                            |
| --------- | ---------------------------------------------------------------- |
| `DEBUG`   | Request sent (method + URL only — no body, no credentials)       |
| `DEBUG`   | Response received (method + URL + status code)                   |
| `DEBUG`   | Retry attempt (attempt number, delay, reason)                    |
| `DEBUG`   | Retryable status code received                                   |
| `WARNING` | All retry attempts exhausted (method + URL + final status/error) |
| `WARNING` | 401 reactive re-auth triggered                                   |

Credentials and request/response bodies are **never** logged by default.

### 3. `LoggingMiddleware` and `AsyncLoggingMiddleware`

All middleware in Plynt operates at the **transport level** via the
`handle(request, next_handler)` chain-of-responsibility contract (ADR-0013).
Middleware fires exactly once per logical HTTP call, outside the retry loop.

Plynt does not emit `INFO` records from the transport internals. `INFO`-level
call visibility is a **service-layer concern**: the service implementor opts
in by injecting `LoggingMiddleware` when constructing the transport.

```python
from plynt.middleware.logging import LoggingMiddleware
from plynt.http.transport import HttpxSyncTransport

transport = HttpxSyncTransport(middlewares=[LoggingMiddleware()])
```

This emits two records per logical call via the `plynt.middleware.logging`
logger (fires once, regardless of the number of retry attempts):

| Level  | Event                                                         |
| ------ | ------------------------------------------------------------- |
| `INFO` | `--> METHOD URL` (before delegating to next handler)          |
| `INFO` | `<-- STATUS METHOD URL  (NNNms)` (after next handler returns) |

Elapsed time is measured with `time.monotonic()` and included in every
response log line. The timestamp is captured by `_log_request()` and passed
to `_log_response()` — subclasses that override both must forward the value.

The log level is configurable via the `level` constructor argument.
The logger is configurable via the `logger` constructor argument.

Both classes expose two protected methods for subclassing:

- `_log_request(request) -> float` — logs the outgoing request and returns
  a `time.monotonic()` snapshot for elapsed-time calculation.
- `_log_response(request, response, start)` — logs the received response
  including elapsed time computed from `start`.

Override either method to change the message format, filter by status code,
or add extra fields. The `start` float must be threaded through both.

### Arrow convention

All Plynt log lines that represent an outgoing request or incoming response
use the same directional prefix regardless of where in the stack they
originate (transport internals, auth middleware, logging middleware):

| Prefix | Meaning                                 |
| ------ | --------------------------------------- |
| `-->`  | Call is leaving Plynt toward the remote |
| `<--`  | Response has arrived back into Plynt    |

This makes it possible to read a mixed-logger DEBUG trace in sequence
without needing to understand which subsystem emitted each line.

For **domain-level logging** (e.g. `"Invoice 42 retrieved"`) — log inside
the service endpoint method where the domain context is available. The
middleware layer is not the right place for this.

### 4. Opt-in body logging

For debugging purposes, body logging can be enabled explicitly per transport
instance via the `log_bodies` constructor flag. This flag is `False` by
default and must never be enabled in production.

```python
transport = HttpxSyncTransport(log_bodies=True)
```

When `log_bodies=True`:

- The request body and response body are logged at `DEBUG` level.
- All headers are scrubbed before logging (see § 4 below).
- The log records carry the field `body_logging=True` to make it easy to
  filter or alert on their presence in a log-aggregation pipeline.

The flag is not exposed via `HTTPSettings` or environment variables —
requiring code changes makes accidental production enablement less likely.

### 5. Credential scrubbing

When `log_bodies=True`, headers are scrubbed before any logging. The
following headers are replaced with `"[REDACTED]"`:

- `Authorization`
- `Cookie`
- `Set-Cookie`
- `X-Api-Key`
- `Proxy-Authorization`

Scrubbing is case-insensitive. The original `Request` and `Response`
objects are never mutated — scrubbing is applied to a copy created solely
for the log record.

### 6. `ThrottleLogs` filter — `plynt.log.filters`

Suppresses repeated log records once a per-window count limit is reached.

```python
class ThrottleLogs(logging.Filter):
    def __init__(
        self,
        name: str | None = None,
        *,
        limit: int = 60,
        pattern: Pattern[str] | None = None,
        window: int = 3600,
    ) -> None: ...
```

- `name` — logger name prefix to target (e.g. `"plynt.http"`). `None`
  targets all loggers.
- `limit` — maximum matching records per window before suppression. `0`
  suppresses from the very first record.
- `pattern` — optional compiled regex; only matching messages are counted.
- `window` — rolling window in seconds (default: 3600).
- Thread-safe. Non-targeted records always pass through.

### 7. `ExceptionInfoFilter` filter — `plynt.log.filters`

Injects active exception context into records that were emitted without
`exc_info`, so formatters and Sentry see the full traceback.

```python
class ExceptionInfoFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool: ...
```

- Never suppresses records — always returns `True`.
- Checks `sys.exc_info()` and attaches it when an exception is active.
- Records that already carry `exc_info` are left untouched.

### 8. `PlyntHTTPFilter` filter — `plynt.log.filters`

Convenience subclass of `ThrottleLogs`, pre-configured for the
`plynt.http` logger namespace with sensible defaults.

```python
class PlyntHTTPFilter(ThrottleLogs):
    def __init__(self, *, limit: int = 60, window: int = 3600) -> None:
        super().__init__(name="plynt.http", limit=limit, window=window)
```

Operators can attach it to any handler with zero extra configuration:

```python
from plynt.log import PlyntHTTPFilter

handler.addFilter(PlyntHTTPFilter())
```

### 9. `StructuredFormatter` formatter — `plynt.log.formatter`

Renders each log record as a single-line JSON object. Fields:

| Field      | Source                                           |
| ---------- | ------------------------------------------------ |
| `time`     | `record.created` (ISO 8601, UTC)                 |
| `level`    | `record.levelname`                               |
| `logger`   | `record.name`                                    |
| `message`  | formatted message                                |
| `exc_info` | formatted exception string — omitted when absent |

Suitable for log-aggregation pipelines (ELK, Cloud Logging, Datadog, etc.).
No extra dependencies.

#### Current limitation — extra fields are dropped

~~`StructuredFormatter` currently only serialises the five fields above.~~

`StructuredFormatter` serialises the five fixed fields above **plus** any
structured data attached via `extra={}` on the logging call. Extra keys
present on the `LogRecord` that are not part of the standard
`logging.LogRecord` attribute set are included in the JSON output using
their original key names.

#### ECS-aligned extra fields

Plynt uses [Elastic Common Schema (ECS)](https://www.elastic.co/guide/en/ecs/current/index.html)
field names for HTTP events. The following fields are emitted on every
request/response log record from `LoggingMiddleware` and the transport:

| ECS field                   | Type  | Meaning                                                                           |
| --------------------------- | ----- | --------------------------------------------------------------------------------- |
| `event.action`              | `str` | Always `"http-request"`                                                           |
| `http.request.method`       | `str` | `GET`, `POST`, …                                                                  |
| `http.response.status_code` | `int` | `200`, `404`, … (response records only)                                           |
| `url.full`                  | `str` | Full request URL                                                                  |
| `event.duration`            | `int` | Elapsed time in **nanoseconds** (response records only, `LoggingMiddleware` only) |

ECS nanoseconds align with OpenTelemetry semantic conventions and can be
directly ingested by Filebeat, APM Server, and Datadog without remapping.

The human-readable `message` string retains the `-->` / `<--` format for
terminal readability; the structured fields carry the machine-readable values
for log-aggregation queries.

### 10. Django `LOGGING` configuration example

```python
LOGGING = {
    "version": 1,
    "formatters": {
        "json": {"()": "plynt.log.StructuredFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["plynt_http"],
        },
    },
    "filters": {
        "plynt_http": {"()": "plynt.log.PlyntHTTPFilter"},
    },
    "loggers": {
        "plynt": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
```

## Consequences

- All logging decisions for Plynt are documented in a single ADR.
- Operators have a single `plynt.*` namespace to configure verbosity.
- Retry events and auth refreshes are observable without patching internals.
- `PlyntHTTPFilter` eliminates boilerplate for flood protection.
- `StructuredFormatter` provides JSON output with no extra dependencies.
- `LoggingMiddleware` and `AsyncLoggingMiddleware` provide opt-in `INFO`-level
  call logging including elapsed time, without touching the transport internals.
- All Plynt log lines use the `-->` / `<--` arrow convention consistently
  across the transport and middleware layers.
- Subclassing `_log_request` / `_log_response` allows services to filter by
  status code, change the log level, or add extra fields without forking.
- `StructuredFormatter` serialises the five fixed fields plus any ECS-aligned
  `extra` fields present on the record, making HTTP events queryable in
  log-aggregation pipelines without parsing the message string.
- Body logging is strictly opt-in and requires a code change, reducing the
  risk of accidental production enablement.
- Scrubbing of sensitive headers is mandatory when bodies are logged.
- Credentials and bodies are never exposed in the default (always-on) path.

## Explicitly out of scope

- **`TracingMiddleware` (`plynt[otel]`)**: a dedicated plynt middleware for
  OpenTelemetry tracing is not needed. `opentelemetry-instrumentation-httpx`
  instruments httpx2 automatically and covers the common tracing use case
  (spans, HTTP semantic conventions) without any plynt-specific code. A
  plynt middleware would only add value for chain-position-aware span
  boundaries (latency measured after auth + retry, not raw httpx2 latency).
  No demonstrated demand exists; no ADR will be written unless that changes.
- **`MetricsMiddleware` (`plynt[prometheus]`)**: a dedicated prometheus
  metrics middleware is not needed. `opentelemetry-instrumentation-httpx`
  combined with an OTel Prometheus exporter already provides request counts
  and latency histograms. A plynt middleware would only add value for
  callers who need Prometheus metrics independent of OTel. No demonstrated
  demand exists; no ADR will be written unless that changes.

## References

- ADR-0013: Transport Base Class
- ADR-0012: Retry Strategy
- ADR-0011: Authentication
