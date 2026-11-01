# Migrate to typed transport and authentication errors

This guide covers the intentional error-contract changes approved by
[ADR-0039](../../architecture/adr/0039-typed-transport-and-authentication-errors.md).
They are breaking changes under the
[pre-1.0 versioning policy](../../architecture/adr/0035-pre-1-versioning-policy.md).
Review this guide before upgrading across a 0.x release containing these
changes. Release automation selects version numbers; this guide does not
identify a release version.

## What changed

| Failure                                                          | Previous behavior                                           | Current behavior                                                                         |
| ---------------------------------------------------------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Built-in HTTP transport timeout                                  | Raised an `httpx2` timeout exception                        | Raises `TransportTimeoutError`                                                           |
| Built-in HTTP transport network failure                          | Raised an `httpx2` network exception                        | Raises `TransportConnectionError`                                                        |
| OAuth2 or Salesforce token endpoint response other than HTTP 200 | Raised `RuntimeError` with the response body in its message | Raises `AuthenticationError` with `status_code`; the body is not included in its message |

Both typed transport exceptions inherit from `TransportError`. Built-in sync
and async HTTP transports preserve the original backend exception in
`__cause__`, but do not copy its message into the Plynt exception. Local
protocol and programming errors remain unchanged. Failures while consuming an
already returned stream continue to use `StreamInterruptedError`.

`AuthenticationError` inherits from both `TransportError` and `RuntimeError`.
It exposes `status_code` and an optional raw `response_body` attribute. The
body is excluded from `str()`, `repr()`, exception arguments, and structured
error output. Treat the attribute as sensitive and do not log it. Existing
`except RuntimeError` handlers continue to catch token endpoint failures.
Missing or empty `instance_url` in a successful Salesforce token response
continues to raise `RuntimeError`.

## Update exception handlers

Replace handlers for backend HTTP network exceptions with Plynt's public
transport types:

```python
from plynt.base import TransportConnectionError, TransportTimeoutError

try:
    response = client.get("/items")
except TransportTimeoutError:
    print("Upstream request timed out")
except TransportConnectionError:
    print("Upstream connection failed")
```

These types cover network failures from Plynt's built-in HTTP transports.
Custom transports can still raise their own exception types. Keep a separate
handler for other failures if your application uses a custom transport.

For token failures, inspect `status_code` instead of parsing the old
`RuntimeError` message:

```python
from plynt.base import AuthenticationError

try:
    client.get("/items")
except AuthenticationError as error:
    print(f"Authentication endpoint returned {error.status_code}")
```

Do not include `response_body` in logs or error reports. It can contain
sensitive authentication response data.

## Check retry configuration

The default `HttpRetryPolicy` recognizes `TransportTimeoutError` and
`TransportConnectionError` as retryable network failures. It also retains
recognition of raw `httpx2` network exceptions for custom transports when the
optional HTTP backend is installed.

The HTTP policy defaults to three total attempts, retries network errors, and
retries status codes `429`, `500`, `502`, `503`, and `504`. An explicit
`retryable_exception_classifier` replaces the default classifier. Update a
custom classifier that only recognizes `httpx2` exceptions to include the new
Plynt types. Status-code defaults are also replaced when you pass an explicit
`retryable_status_codes` set.

The protocol-agnostic `RetryPolicy` has no HTTP status-code defaults. Its
default classifier recognizes built-in `TimeoutError`, `ConnectionError`, and
`OSError`, but not Plynt's typed transport exceptions. If a custom transport
raises those types and uses `RetryPolicy`, supply a classifier that recognizes
them.

## Related documentation

- [Error handling](../how-to/handle-errors.md) describes the full exception
  hierarchy, HTTP status errors, streams, and raw response mode.
- [Salesforce error handling](../../connectors/salesforce/user/how-to/handle-errors.md)
  documents connector-specific errors and token failures.
- [Request ID context](../how-to/use-request-id-context.md) and
  [error reporting](../how-to/report-errors.md) describe adjacent observability
  contracts introduced with this release scope.
- [FastAPI error envelopes](../../adapters/fastapi/configure-error-envelopes.md)
  and [DRF error envelopes](../../adapters/django/drf/configure-error-envelopes.md)
  document adapter response mapping, which is separate from these transport
  and authentication exceptions.
- [FastAPI/Salesforce lifespan recipe](../../connectors/salesforce/user/how-to/use-fastapi-lifespan.md)
  documents application-scoped auth, transport ownership, and shutdown.
- Framework-specific guides now live in the
  [adapter documentation](../../adapters/README.md); the index links to Django,
  DRF, and FastAPI guides.
