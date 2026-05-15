# How to configure logging

Plynth uses the standard Python `logging` module. This guide explains the
logger hierarchy, how to enable request/response logging, and how to
produce structured JSON output suitable for log aggregation.

## Logger hierarchy

| Logger name             | What it emits                                    |
| ----------------------- | ------------------------------------------------ |
| `plynth`                | Parent; configure once to affect all children    |
| `plynth.base`           | Retry attempts, auth refreshes (DEBUG / WARNING) |
| `plynth.http.transport` | Per-request send/receive events (DEBUG)          |
| `plynth.http`           | INFO-level timing logs from `LoggingMiddleware`  |

## Step 1 — Enable INFO-level request logging

Add `LoggingMiddleware` to your transport and set the log level:

```python
import logging
from plynth.middleware.logging import LoggingMiddleware
from plynth.http.transport import HttpxSyncTransport

logging.getLogger("plynth").setLevel(logging.INFO)

transport = HttpxSyncTransport(middlewares=[LoggingMiddleware()])
```

Each request logs a line like:

```text
INFO plynth.http GET https://api.example.com/items → 200 (45ms)
```

## Step 2 — Enable DEBUG transport logs

Set `plynth.http.transport` to DEBUG to see low-level send/receive events:

```python
logging.getLogger("plynth.http.transport").setLevel(logging.DEBUG)
```

## Step 3 — Use structured JSON logging

`StructuredFormatter` emits single-line JSON objects with a fixed schema:

```python
import logging
from plynth.log import StructuredFormatter
from plynth.middleware.logging import LoggingMiddleware
from plynth.http.transport import HttpxSyncTransport

handler = logging.StreamHandler()
handler.setFormatter(StructuredFormatter())

root_logger = logging.getLogger("plynth")
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

transport = HttpxSyncTransport(middlewares=[LoggingMiddleware()])
```

Each log line is a JSON object:

```json
{
  "time": "2026-05-15T12:00:00.000Z",
  "level": "INFO",
  "logger": "plynth.http",
  "message": "GET https://api.example.com/items → 200 (45ms)"
}
```

Any `extra={}` fields on a logging call are included as additional keys.

## Step 4 — Throttle noisy logs

`ThrottleLogs` suppresses repeated log records after a configurable
per-window count. Use it to prevent log flooding from a chatty upstream:

```python
from plynth.log import ThrottleLogs

handler = logging.StreamHandler()
handler.addFilter(
    ThrottleLogs(name="plynth.http", limit=10, window=3600)
    # Allow at most 10 plynth.http records per hour; suppress the rest
)
logging.getLogger("plynth").addHandler(handler)
```

## Step 5 — Add exception info to non-exception log records

`ExceptionInfoFilter` injects active exception context into records that
were emitted without it. Useful when you catch exceptions and log them
manually without `exc_info=True`:

```python
from plynth.log import ExceptionInfoFilter

handler = logging.StreamHandler()
handler.addFilter(ExceptionInfoFilter())
```

## Step 6 — Use PlynthHTTPFilter as a convenience wrapper

`PlynthHTTPFilter` is a pre-configured `ThrottleLogs` subclass for the
`plynth.http` logger with sensible defaults (60 records per hour):

```python
from plynth.log import PlynthHTTPFilter

handler = logging.StreamHandler()
handler.addFilter(PlynthHTTPFilter())
logging.getLogger("plynth").addHandler(handler)
```

## Async

Use `AsyncLoggingMiddleware` with `HttpxAsyncTransport`. The log formatter,
filters, and logger hierarchy are the same.

## Reference

- `StructuredFormatter` — `plynth.log.formatter`
- `ThrottleLogs`, `ExceptionInfoFilter`, `PlynthHTTPFilter` — `plynth.log.filters`
- `LoggingMiddleware`, `AsyncLoggingMiddleware` — `plynth.middleware.logging`
