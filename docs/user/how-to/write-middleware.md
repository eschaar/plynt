# How to write custom middleware

Plynth middleware is a pair of protocols — `SyncMiddleware` and
`AsyncMiddleware`. Implement the `handle` method and insert your class into
a transport's `middlewares` list.

## The protocols

```python
# plynth.base.middleware

class SyncMiddleware(Protocol):
    def handle(self, request: Request, next_handler: NextSyncHandler) -> Response: ...

class AsyncMiddleware(Protocol):
    async def handle(
        self, request: Request, next_handler: NextAsyncHandler
    ) -> Response: ...
```

`next_handler` is a callable that sends the request to the next middleware
in the chain (and ultimately to the network). Always call it unless you
intend to short-circuit the chain.

## Example: request timing middleware

```python
import time
import logging
from plynth.base.middleware import NextSyncHandler
from plynth.base.request import Request
from plynth.base.response import Response

logger = logging.getLogger(__name__)


class TimingMiddleware:
    """Log the round-trip duration of every outbound request."""

    def handle(self, request: Request, next_handler: NextSyncHandler) -> Response:
        start = time.monotonic()
        response = next_handler(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info("%s %s → %s (%dms)", request.method, request.url,
                    response.status_code, elapsed_ms)
        return response
```

## Example: inject a request header

```python
class CorrelationHeaderMiddleware:
    """Inject a correlation ID header on every outbound request."""

    def __init__(self, header_name: str = "X-Correlation-ID") -> None:
        self._header_name = header_name

    def handle(self, request: Request, next_handler: NextSyncHandler) -> Response:
        import uuid
        headers = dict(request.headers)
        headers.setdefault(self._header_name, str(uuid.uuid4()))
        return next_handler(Request(
            method=request.method,
            url=request.url,
            headers=headers,
            content=request.content,
        ))
```

## Example: short-circuit on a condition

Return a `Response` directly without calling `next_handler` to prevent the
request from reaching the network:

```python
from plynth.base.response import Response


class MaintenanceModeMiddleware:
    """Return 503 during maintenance windows without making network calls."""

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled

    def handle(self, request: Request, next_handler: NextSyncHandler) -> Response:
        if self._enabled:
            return Response(
                status_code=503,
                headers={"Content-Type": "application/json"},
                content=b'{"error": "maintenance"}',
            )
        return next_handler(request)
```

## Example: transform the response

```python
class StatusNormalizationMiddleware:
    """Convert 204 No Content to 200 with an empty JSON body."""

    def handle(self, request: Request, next_handler: NextSyncHandler) -> Response:
        response = next_handler(request)
        if response.status_code == 204:
            return Response(
                status_code=200,
                headers=dict(response.headers) | {"Content-Type": "application/json"},
                content=b"{}",
            )
        return response
```

## Example: handle or re-raise exceptions

```python
import logging
from plynth.http.errors import HttpStatusError

logger = logging.getLogger(__name__)


class ErrorLoggingMiddleware:
    """Log HTTP errors before re-raising them."""

    def handle(self, request: Request, next_handler: NextSyncHandler) -> Response:
        try:
            return next_handler(request)
        except HttpStatusError as exc:
            logger.warning("HTTP error: %s %s → %s", request.method,
                           request.url, exc.response.status_code)
            raise
```

## Async variant

Implement `async def handle(...)` and use with `HttpxAsyncTransport`:

```python
from plynth.base.middleware import NextAsyncHandler


class AsyncTimingMiddleware:
    async def handle(self, request: Request, next_handler: NextAsyncHandler) -> Response:
        import time
        start = time.monotonic()
        response = await next_handler(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info("%s %s → %s (%dms)", request.method, request.url,
                    response.status_code, elapsed_ms)
        return response
```

## Middleware ordering

The first middleware in the list is the outermost. Put cross-cutting
concerns like caching and logging early; put network-dependent concerns
like retry and circuit breaking later:

```python
middlewares = [
    TimingMiddleware(),          # outermost
    LoggingMiddleware(),
    auth_middleware,
    RetryMiddleware(...),
    CircuitBreakerMiddleware(...),
]
```

See [Middleware model explanation](../explanation/middleware-model.md) for
details on ordering.

## Reference

- All built-in middleware classes and their policies:
  [Middleware reference](../reference/middleware.md).
