# ADR-0043: Exception-Bound Error Event IDs

**Date:** 2026-11-01
**Status:** Accepted

## Context

[ADR-0041](0041-error-tracking-integration-and-sentry-extra.md) requires opt-in
event IDs in error envelopes. Outbound reporting scopes finish before inbound
exception handlers run. FastAPI also transfers exceptions from synchronous
workerthreads without transferring their changed ContextVars back.

A request may contain several outbound calls, including failures that the
application handles. A context-wide last ID could therefore identify an
unrelated event. The exception's existing message/code/details payload must
remain backward compatible.

## Decision

Associate a validated event ID with the exact exception passed to the reporter,
using private immutable reporting metadata on that exception.

- Expose `get_error_event_id(exc)` for custom error envelopes. Do not search
  causes or contexts: wrapping an error does not implicitly transfer its ID.
- Clear previous reporting metadata before each reporting attempt. A reporter
  returning None, raising, or returning an invalid ID leaves no publishable ID.
- Accept non-empty ASCII identifiers up to 128 characters containing letters,
  digits, underscores, dots, colons, or hyphens. Reject other values with safe
  diagnostics while preserving the original exception.
- Do not change exception identity, arguments, message, code, or details.
  Private reporting metadata is not a new serialized error-data bucket.
- Keep default responses and the three-argument envelope callable unchanged.
  Applications opt in by reading the helper in their custom envelope.
- Do not add a global last-event cache, another ContextVar, framework dependency,
  or event-ID generation. The association lasts as long as the exception.

This decision clarifies ADR-0041's last-event wording: use the last reporting
result for the specific exception, never the last event for another failure.

## Alternatives Considered

### ContextVar holding the last event

Execution-local state avoids a global cache, but outbound scope reset loses the
ID before envelope construction. Workerthread updates also cannot reliably
reach the async framework handler. Rejected.

### Add the ID to exception details

The details mapping already provides external error data, but reporting would
mutate application-owned data and expose tracker metadata whenever callers
enable details. Generic exceptions also have no such mapping. Rejected.

### Global exception-to-event registry

This avoids exception metadata, but adds synchronization and cleanup. Standard
exceptions cannot generally be weak-referenced, so a registry could retain
exceptions, tracebacks, and application data indefinitely. Rejected.

## Rationale

Frameworks already transfer the original exception across execution boundaries.
A small receipt follows that same object without new lifecycle management.
Exact-exception lookup prevents stale correlation after handled earlier errors.
Existing envelope injection supplies opt-in serialization without adapter flags
or a new callback shape.

## Consequences

### Positive

- Works for sync and async reporting, including framework workerthreads.
- Keeps default error responses and application-owned details unchanged.
- Uses no new dependencies or execution-local state.

### Negative / Tradeoffs

- Private metadata is visible to exception introspection.
- Applications must use distinct exception instances for distinct failures.
  Concurrently reporting a shared exception has no defined event ordering.
- Wrapping an exception intentionally requires explicit application handling.

### Risks

- Reusing an exception can retain an earlier ID unless reporting clears it.
  Tests cover missing IDs, failures, invalid results, and repeated reporting.
- Custom exceptions can prevent metadata access. Treat this as a reporting
  failure with safe diagnostics; never replace the original chain exception.

## Related ADRs

- [ADR-0040](0040-inbound-request-id-and-error-envelope.md): envelope callable.
- [ADR-0041](0041-error-tracking-integration-and-sentry-extra.md): reporting IDs.
- [ADR-0042](0042-error-reporting-context-handoff.md): outbound observation scope.
