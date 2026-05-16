# How to handle errors

Plynth maps HTTP status codes to typed Python exceptions. Catch the most
specific exception you need and let the rest propagate.

## Core exception hierarchy

```bash
Exception
└── RuntimeError
    ├── TransportError                   (plynth.base.errors)
    │   └── StatusError                  (plynth.base.errors)
    │       └── HttpStatusError          (plynth.http.errors)
    │           ├── BadRequestError      (400)
    │           ├── UnauthorizedError    (401)
    │           ├── ForbiddenError       (403)
    │           ├── NotFoundError        (404)
    │           ├── NotAllowedError      (405)
    │           ├── RequestTimeoutError  (408)
    │           ├── ConflictError        (409)
    │           ├── GoneError            (410)
    │           ├── UnprocessableEntityError (422)
    │           ├── InternalServerError  (500)
    │           ├── OperationFailedError (500)
    │           ├── ServiceUnavailableError (503)
    │           └── FeatureOfflineError  (503)
    ├── CircuitBreakerOpenError          (plynth.middleware.circuit_breaker)
    └── RateLimitExceededError           (plynth.middleware.rate_limit)
```

## Catch HTTP status errors

`APIClient` raises `HttpStatusError` (or a subclass) for `4xx` and `5xx` responses.

```python
from plynth.http.errors import NotFoundError, HttpStatusError

try:
    response = client.get("/items/42")
except NotFoundError:
    print("Item does not exist")
except HttpStatusError as exc:
    print(f"HTTP error {exc.status_code}: {exc.url}")
```

The `response` attribute on the exception holds the raw response:

```python
except HttpStatusError as exc:
    body = exc.response.json() if exc.response else {}
```

## Bypass typed mapping with raw mode

`APIClient` raises `HttpStatusError` for `4xx` and `5xx` responses by
default. Responses with a `1xx`, `2xx`, or `3xx` status code are returned
directly without any exception mapping — no flag is needed for those.

Use `raw=True` only when you need to receive a `4xx` or `5xx` response
without an exception:

```python
response = client.get("/items/42", raw=True)

if response.status_code == 404:
    print("Item does not exist")
```

Typical use cases:

- Inspect the body of a `4xx` error response that carries a structured
  payload before deciding how to handle it.
- Forward upstream `4xx`/`5xx` responses to another service without
  triggering local error handling.
- Write test helpers that need to assert on error response details.

Note: `HTTPClient` already behaves as a raw client. The `raw` toggle is only
needed when using `APIClient` or `AsyncAPIClient`.

## Construct a typed error from a status code

Use `match_error` to get the most specific subclass for a known status code:

```python
from plynth.http.errors import match_error

err = match_error(404, method="GET", url="/items/1")
# err is a NotFoundError instance
```

## Catch circuit breaker errors

```python
from plynth.middleware.circuit_breaker import CircuitBreakerOpenError

try:
    response = client.get("/items")
except CircuitBreakerOpenError as exc:
    print(f"Circuit open — retry after {exc.retry_after_seconds:.0f}s")
```

## Catch rate limit errors

```python
from plynth.middleware.rate_limit import RateLimitExceededError

try:
    response = client.post("/items", json={"name": "x"})
except RateLimitExceededError:
    print("Client-side rate limit hit — slow down")
```

## Let unexpected errors propagate

Not every exception needs to be caught at the call site. Let unexpected
errors propagate to your application's central error handler (Sentry,
logging middleware, framework error handler, etc.).

## Connector-specific errors

Connectors extend `HttpStatusError` with domain-specific subclasses. See
the connector's own error reference for details. For example:

- [Salesforce — handle errors](../../connectors/salesforce/user/how-to/handle-errors.md)
