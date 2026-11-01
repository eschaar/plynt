# Use request IDs with FastAPI and ASGI

Wrap the application with the pure ASGI `RequestIDMiddleware`:

```python
from fastapi import FastAPI
from plynt.adapters.fastapi import RequestIDMiddleware
from plynt.base import RequestIDPolicy, get_request_id

api = FastAPI()


@api.get("/items/")
async def items() -> dict[str, str | None]:
    return {"request_id": get_request_id()}


app = RequestIDMiddleware(api, policy=RequestIDPolicy(trust_inbound=False))
```

Serve the exported `app`. Configure routes, dependencies, lifespan, and
exception handlers on `api` before wrapping it.

The middleware uses ASGI directly, not `BaseHTTPMiddleware`. It can wrap any
ASGI application, despite being exposed through the FastAPI adapter package.
There are no FastAPI or Starlette runtime imports in the middleware module.

## Scope and validation

HTTP requests receive one validated inbound ID or a generated replacement.
The default header is `X-Request-ID`. Missing, invalid, or duplicate inbound
headers cause a replacement; rejected values are never echoed.

The default policy trusts valid inbound IDs. Use `trust_inbound=False` for
services that should always generate their own ID. A custom `RequestIDPolicy`
also controls the header name, maximum length, and generator.

Sync FastAPI endpoints receive the ID through the framework's copied worker
context. Async endpoints use their task-local context. The ID remains active
throughout the ASGI HTTP call, including streaming-body sends, and is restored
when the call returns, raises, or is cancelled.

WebSocket and lifespan scopes pass through unchanged, without creating an ID.
Detached background tasks can inherit context; applications own their lifetime
and must establish a new scope for independent work.

## Response headers and ordering

Wrapping the whole app places the middleware before router slash redirects
and outside the framework's error middleware. This ensures `307` redirects
and framework-generated `500` responses carry the request ID.

Using `api.add_middleware(RequestIDMiddleware)` is also possible, but places it
inside the framework's outer error middleware; unhandled-error responses
created outside it may then lack the header. Prefer the outer wrapper.

The middleware adds the ID on `http.response.start`, replacing all existing
case-insensitive matches. It preserves other headers, response statuses, and
body messages without modifying the application's original message.

It never changes paths or `redirect_slashes`. Redirects and final requests are
separate scopes; retaining the same ID requires the caller to send it again.
If an app raises before sending a response, the middleware propagates the
exception instead of inventing an error response.

## Outbound calls and logging

Request-ID propagation and logging remain explicit opt-ins:

- Configure `AsyncHeaderMiddleware` or `HeaderMiddleware` with
  `request_id_policy` for outbound calls.
- Attach `RequestIDFilter` to logging handlers.

See the [core request-ID guide](../../user/how-to/use-request-id-context.md)
for configuration and request-versus-workflow semantics.

Custom FastAPI error envelopes are a subsequent ADR-0040 step; this middleware
only manages context and response headers.
