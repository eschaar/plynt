# Report middleware-chain failures

Reporting is opt-in. Inject an `ErrorReporter` into `ErrorReportingMiddleware`
or `AsyncErrorReportingMiddleware`; the core supplies no backend.

```python
from plynt.base import ErrorReporter, Request
from plynt.middleware import ErrorReportingMiddleware


def domain_context(request: Request) -> dict[str, str]:
    return {"connector": "example", "service": "items", "operation": "fetch"}


def reporting(reporter: ErrorReporter) -> ErrorReportingMiddleware:
    return ErrorReportingMiddleware(reporter, context_provider=domain_context)
```

Place reporting outside retry middleware to capture the final exception once
and observe delegated attempt counts. The synchronous provider works in both
execution modes and must not perform I/O.

Only `connector`, `service`, and `operation` are accepted from the provider.
Use non-empty printable identifiers up to 128 characters and never include
credentials or personal data. Unknown fields and invalid values cause safe
logging rather than vendor dispatch.

Request context contains the method and URL with sensitive query values
redacted using logging rules. URL user information and fragments are omitted.
Malformed URLs are omitted with a safe diagnostic; the exception is still
reported without the URL.
Bodies, request parameters, arbitrary headers, and exception details are not
automatically added. Non-sensitive query values and paths remain visible;
applications must not put secrets or personal data there.

Observed `attempts` count delegated retry-loop calls, not wire sends. `retries`
is attempts after the first. Without retry observation these fields are absent,
not inferred from configured maximums. Nested scopes and concurrent calls
keep their counters independent.
Reporting uses one immutable execution-local state, replaced on updates.
It is separate from the longer-lived inbound request-ID context.

Status-bearing errors supply `upstream_status`. An attached response can supply
a validated `X-Request-ID` as `upstream_request_id`; outgoing headers are never
misrepresented as upstream response IDs.

The original exception is passed to the reporter and re-raised unchanged.
Reporters own safe handling of exception data, including tracebacks and causes.
Provider or reporter failures log a fixed diagnostic without their exception
messages and preserve the original failure. Cancellation and process-control
exceptions propagate without being swallowed.

Returned error statuses are not exceptions and are not reported. Failures while
iterating an already returned stream are outside this middleware's scope.

## Opt in to event IDs in responses

A reporter may return an event ID, or None when no event was captured. IDs must
use 1-128 ASCII letters, digits, underscores, dots, colons, or hyphens.
Invalid results log a safe diagnostic and are not published.

`get_error_event_id(exc)` reads the ID for that exact exception after reporting
finishes. The immutable receipt follows the exception into a framework handler,
including from FastAPI workerthreads. No context-wide last ID is used.

Default responses remain unchanged. Pass a custom envelope to the FastAPI
handler helpers or the DRF exception handler to explicitly publish the ID:

```python
from plynt.base import default_error_envelope, get_error_event_id


def envelope(
    exc: Exception, status_code: int, request_id: str | None
) -> dict[str, object]:
    payload = default_error_envelope(exc, status_code, request_id)
    event_id = get_error_event_id(exc)
    if event_id is not None:
        payload["error_id"] = event_id
    return payload
```

For FastAPI, use `install_plynt_exception_handlers(app, envelope=envelope)`.
For DRF, pass `envelope=envelope` from your application exception handler to
`plynt_exception_handler(exc, context, envelope=envelope)`.

Unreported exceptions have no ID, even after an earlier handled failure in the
same request. Wrapped exceptions do not inherit a cause's ID. Each reporting
attempt clears an earlier receipt before invoking the provider or reporter;
None, failure, or cancellation leaves no stale ID. Do not reuse one exception
instance for concurrent independent failures.

This does not change exception arguments or the message/code/details payload.
For vendor setup, see the optional [Sentry integration](../../integrations/sentry.md).
