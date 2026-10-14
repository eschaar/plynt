# How to configure logging

Plynt uses the standard Python `logging` module. This guide explains the
logger hierarchy, how to enable request/response logging, and how to
produce structured JSON output suitable for log aggregation.

## Logger hierarchy

| Logger name            | What it emits                                    |
| ---------------------- | ------------------------------------------------ |
| `plynt`                | Parent; configure once to affect all children    |
| `plynt.base`           | Retry attempts, auth refreshes (DEBUG / WARNING) |
| `plynt.http.transport` | Per-request send/receive events (DEBUG)          |
| `plynt.http`           | INFO-level timing logs from `LoggingMiddleware`  |

## Step 1 — Enable INFO-level request logging

Add `LoggingMiddleware` to your transport and set the log level:

```python
import logging
from plynt.middleware.logging import LoggingMiddleware
from plynt.http.transport import HttpxSyncTransport

logging.getLogger("plynt").setLevel(logging.INFO)

transport = HttpxSyncTransport(middlewares=[LoggingMiddleware()])
```

Each request logs a line like:

```text
INFO plynt.http GET https://api.example.com/items → 200 (45ms)
```

## Step 2 — Enable DEBUG transport logs

Set `plynt.http.transport` to DEBUG to see low-level send/receive events:

```python
logging.getLogger("plynt.http.transport").setLevel(logging.DEBUG)
```

## Step 3 — Use structured JSON logging

`StructuredFormatter` emits single-line JSON objects with a fixed schema:

```python
import logging
from plynt.log import StructuredFormatter
from plynt.middleware.logging import LoggingMiddleware
from plynt.http.transport import HttpxSyncTransport

handler = logging.StreamHandler()
handler.setFormatter(StructuredFormatter())

root_logger = logging.getLogger("plynt")
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

transport = HttpxSyncTransport(middlewares=[LoggingMiddleware()])
```

Each log line is a JSON object:

```json
{
  "time": "2026-05-15T12:00:00.000Z",
  "level": "INFO",
  "logger": "plynt.http",
  "message": "GET https://api.example.com/items → 200 (45ms)"
}
```

Any `extra={}` fields on a logging call are included as additional keys.

## Step 4 — Throttle noisy logs

`ThrottleLogs` suppresses repeated log records after a configurable
per-window count. Use it to prevent log flooding from a chatty upstream:

```python
from plynt.log import ThrottleLogs

handler = logging.StreamHandler()
handler.addFilter(
    ThrottleLogs(name="plynt.http", limit=10, window=3600)
    # Allow at most 10 plynt.http records per hour; suppress the rest
)
logging.getLogger("plynt").addHandler(handler)
```

## Step 5 — Add exception info to non-exception log records

`ExceptionInfoFilter` injects active exception context into records that
were emitted without it. Useful when you catch exceptions and log them
manually without `exc_info=True`:

```python
from plynt.log import ExceptionInfoFilter

handler = logging.StreamHandler()
handler.addFilter(ExceptionInfoFilter())
```

## Step 6 — Use PlyntHTTPFilter as a convenience wrapper

`PlyntHTTPFilter` is a pre-configured `ThrottleLogs` subclass for the
`plynt.http` logger with sensible defaults (60 records per hour):

```python
from plynt.log import PlyntHTTPFilter

handler = logging.StreamHandler()
handler.addFilter(PlyntHTTPFilter())
logging.getLogger("plynt").addHandler(handler)
```

## Async

Use `AsyncLoggingMiddleware` with `HttpxAsyncTransport`. The log formatter,
filters, and logger hierarchy are the same.

## Reference

- `StructuredFormatter` — `plynt.log.formatter`
- `ThrottleLogs`, `ExceptionInfoFilter`, `PlyntHTTPFilter` — `plynt.log.filters`
- `LoggingMiddleware`, `AsyncLoggingMiddleware` — `plynt.middleware.logging`
