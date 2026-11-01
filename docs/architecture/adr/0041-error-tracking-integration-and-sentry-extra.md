# ADR-0041: Error-Tracking Integration and Sentry Extra

**Date:** 2026-11-01
**Status:** Proposed

## Context

Services report failures to error trackers such as Sentry. The Sentry SDK
already captures unhandled exceptions and instruments httpx calls, but it
does not know plynt context: connector, service, operation, upstream
status, retry attempts, or the upstream request ID. It also does not know
plynt's redaction rules, so auth headers or tokens can reach the tracker.

Callers often need the tracker's event ID in error responses, so support
staff can find the event. Earlier services added this through company
specific middleware. Plynt needs a generic version without vendor lock-in
or organization-specific conventions.

## Decision

Proposed:

1. Add a small `ErrorReporter` protocol in the core with sync and async
   methods that receive an exception and a redacted context mapping and
   return an optional event ID. The core ships no default implementation
   and adds no dependency.
1. Add opt-in middleware that calls the configured reporter for failures
   raised in the middleware chain. Context includes connector, service,
   operation, upstream status, retry attempts, and the upstream request
   ID. Redaction reuses the rules of the logging middleware.
1. Add `plynt.integrations.sentry` behind a new `plynt[sentry]` extra that
   implements the protocol with `sentry-sdk`. It uses the SDK's current
   scope and never initializes the SDK; applications own DSN, sampling,
   environment, and release settings.
1. Expose the last event ID to the error envelope from
   [ADR-0040](0040-inbound-request-id-and-error-envelope.md), so adapters
   can return it, for example as `error_id`, when the application opts in.
1. Do not add organization-specific tags, DSN handling, or environment
   conventions.
1. Add the `sentry` profile to tox extras and the isolated wheel profiles
   per [ADR-0028](0028-supported-environments-and-extras-policy.md).

## Alternatives Considered

### Documentation only

Point users to the Sentry SDK integrations. No redaction or plynt context,
and no event ID in responses. Rejected as incomplete, but the guide is
still written as part of this work.

### Sentry dependency in the core

Violates [ADR-0003](0003-dependency-policy.md). Rejected.

### OpenTelemetry instead

OTel records spans and metrics, not error events with an event ID for
support. Roadmap items 1e and 1f remain separate.

## Rationale

A protocol keeps the core vendor-neutral and testable without a tracker.
Sentry is the most common tracker in Python services, so it is a sensible
first adapter. Other trackers can implement the protocol in a few lines.

## Consequences

### Positive

- Error events carry plynt context without leaking credentials.
- Support can match error responses to tracker events.
- Other trackers can be added as extras without core changes.

### Negative / Tradeoffs

- A new optional dependency and extra to maintain and test.
- One more middleware to place correctly in the chain.

### Risks

- Duplicate events when both the SDK and the middleware capture the
  same exception. Mitigation: report through the SDK's current scope
  and mark events as handled, with a test against duplicate capture.
- `sentry-sdk` releases changing scope APIs. Mitigation: pin a tested
  lower bound and cover the adapter in the wheel profiles.

## Related ADRs

- [ADR-0003](0003-dependency-policy.md): dependency policy.
- [ADR-0013](0013-transport-base-class.md): middleware chain.
- [ADR-0014](0014-logging.md): logging and redaction.
- [ADR-0028](0028-supported-environments-and-extras-policy.md): extras.
- [ADR-0040](0040-inbound-request-id-and-error-envelope.md): envelope.
