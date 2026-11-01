# Report errors to Sentry

Install the optional integration:

```bash
pip install "plynt[sentry]"
```

This extra requires `sentry-sdk>=2.73.0,<3`. Its only added runtime dependencies
are the SDK and its HTTP/certificate dependencies. It does not install a
framework or plynt's built-in HTTP transport. The core works without the extra.

## Application-owned initialization

Initialize Sentry once in application startup using your application's secure
configuration. Plynt never calls `sentry_sdk.init`, reads a DSN, selects sampling,
or sets environment/release conventions.

Inject the reporter into the middleware chain:

```python
from plynt.integrations.sentry import SentryErrorReporter
from plynt.middleware import ErrorReportingMiddleware, AsyncErrorReportingMiddleware

reporter = SentryErrorReporter()
sync_reporting = ErrorReportingMiddleware(reporter)
async_reporting = AsyncErrorReportingMiddleware(reporter)
```

Use the matching middleware outside retry middleware. See
[reporting context and event IDs](../user/how-to/report-errors.md).

## Scope and event safety

Each capture forks the SDK's current scope and restores it afterward.
Application metadata, release, environment, and tags remain available.
Redacted middleware context is stored under the event's `contexts.plynt`.
It does not leak into subsequent unrelated SDK captures.

Plynt events omit automatic request data and breadcrumbs. Exception messages,
cause messages, local variables, source snippets, and `abs_path` frame fields
are also omitted; exception types and basic frame locations remain. Exceptions
are marked with a `plynt` mechanism and `handled=True`.

This deliberately provides less diagnostic detail than ordinary SDK capture.
Exception messages can contain credentials, and upstream error bodies can
contain personal data. Do not bypass these safeguards to expose raw details.

Application-supplied tags, user data, extra fields, custom context, SDK
processors, and `before_send` callbacks remain application-owned.
Callbacks run with the SDK's original exception hint and must not reintroduce
sensitive data. Plynt does not change automatic SDK captures made elsewhere.
Paths and non-sensitive query values in middleware context remain visible;
do not place secrets or personal data there.

## Event IDs and SDK lifecycle

The reporter returns the actual SDK event ID, or None when no event is captured,
for example because the SDK is inactive, sampling drops the event, or
`before_send` returns None. An ID means the SDK accepted an event for capture,
not that the remote server has received it.

Use `get_error_event_id(exc)` from a custom envelope to opt into `error_id`
responses; [the core reporting guide](../user/how-to/report-errors.md#opt-in-to-event-ids-in-responses)
shows this without changing default framework responses.

The async method uses the same SDK enqueue path. Neither method waits for remote
delivery or flushes the SDK. Application callbacks and custom transports execute
synchronously and must not block an async event loop. Applications own flush and
shutdown behavior.

Reporter exceptions propagate to reporting middleware, which logs a fixed safe
diagnostic and preserves the original chain exception.

## Duplicate captures

The integration preserves SDK deduplication and supplies the original exception
hint. With the SDK's standard `DedupeIntegration`, an immediate second capture
of the same exception in the same execution context is dropped. Marking an
event handled does not by itself prevent another capture.

Do not manually capture the same failure in additional application handlers.
SDK deduplication is execution-local: workerthread-to-handler transfers,
separate tasks, disabled deduplication, or intervening exceptions can allow
duplicates. Applications needing broader suppression must coordinate their SDK
capture policy; plynt does not install global hooks or rewrite framework handlers.

## Verification

Tests use the real SDK with an in-memory transport: no event is sent to Sentry.
They cover scope restoration, redaction, sync/async event-ID handoff, SDK
deduplication, dropped events, and missing-extra imports. Isolated wheel
profiles verify both core-only and Sentry installations.
