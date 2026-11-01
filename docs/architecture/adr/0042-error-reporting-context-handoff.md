# ADR-0042: Error-Reporting Context Handoff

**Date:** 2026-11-01
**Status:** Accepted

## Context

[ADR-0041](0041-error-tracking-integration-and-sentry-extra.md) requires
redacted domain context and actual retry counts in reported events.
Transport middleware cannot infer connector, service, or operation names.
`Request` carries wire data only, while retry counters currently remain local
to `RetryMiddleware` and `AsyncRetryMiddleware`.

Guessing names from URLs or reporting configured maximum attempts as actual
attempts would produce misleading telemetry. Adding an arbitrary metadata bag
to every request would broaden the public transport contract for one optional
feature. The missing handoff needs an explicit decision before implementation.

## Decision

Use constructor-injected context providers for domain metadata and a small
execution-local reporting context for observed retry information.

- Reporting middleware accepts an optional synchronous callable receiving the
  request and returning domain context. The same callable works in both
  execution modes and must not perform I/O.
- Supported domain fields are connector, service, and operation. Values are
  explicit application configuration, not inferred from paths or credentials.
  Missing fields remain absent.
- Reporting middleware opens a fresh per-call observation scope.
  Retry middleware updates that scope immediately before each delegated
  attempt. No scope means no telemetry work or retained retry state.
- Store reporting observations in one immutable state value in one ContextVar.
  An absent state means reporting is inactive; an active state with no attempt
  observation keeps counts unavailable. Updates replace the state instead of
  mutating an object shared through copied execution contexts.
- Keep the inbound request-ID context separate: one inbound request may contain
  several independent outbound reporting scopes. No generic context registry
  or contextmanager wrapper is required.
- Record `attempts` as the number of delegated retry-loop calls and
  `retries` as attempts after the first. These are not wire-send counts:
  inner middleware may short-circuit before transport I/O.
- Unobserved counts remain absent, not zero or a configured maximum. Reporting
  must sit outside retry middleware to observe the complete logical call.
- Domain providers cannot override observed execution fields.
- Upstream status and request ID come only from available exception/response
  data. An outbound request ID is not relabeled as an upstream response ID.
- Reuse logging redaction rules for shared request fields. Never automatically
  send bodies, credentials, arbitrary headers, or arbitrary exception details.
- Provider or reporter failures emit safe diagnostics and preserve the original
  application exception. Cancellation and process-control exceptions propagate.
  Reporting is opt-in and must not replace the failure it is meant to observe.

No generic plugin registry, automatic discovery, request metadata bag, or
connector-to-core dependency is introduced.

## Alternatives Considered

### Add arbitrary request metadata

Simple to pass between layers, but broadens every transport request and
encourages mixing domain, telemetry, and wire responsibilities. Rejected.

### Infer context and retry counts

Requires no handoff, but URL inference is unreliable and maximum retries do not
describe actual execution. Rejected because observability must reflect facts.

### Inject providers and scope observed execution data

Keeps domain ownership with applications and attempt ownership with retry
middleware. Uses composition and standard-library execution contexts.
Chosen despite requiring explicit middleware ordering.

## Rationale

This follows the existing callable-based header and classifier extension
patterns. Context providers are a focused extension point, not a general
pluginsystem. Execution-local scopes avoid global counters and allow sync
threads and concurrent async requests to use one middleware instance safely.

Reporting context is separate from the request-ID scope: several outbound
calls can belong to one inbound request, but their attempt counts must not mix.
The event-ID response feature and Sentry adapter remain governed by ADR-0041.

## Consequences

### Positive

- No request-carrier or connector API changes.
- Explicit domain metadata and truthful attempt counts.
- One shared execution-independent mechanism for sync and async reporting.
- Reporting remains optional and vendor-neutral.

### Negative / Tradeoffs

- Applications must configure domain context when needed.
- Middleware ordering determines which attempts can be observed.
- Custom retry implementations need an explicit observation hook to expose
  counts; otherwise those fields are omitted.

### Risks

- Nested or concurrent calls could mix counts. Use a fresh per-call scope,
  restore it in `finally`, and test nesting, task concurrency, and threads.
- Context callbacks could leak sensitive values. Restrict supported fields,
  document caller responsibility, and test redaction before vendor dispatch.
- Telemetry failure could hide the application failure. Test provider and
  reporter failures, including original-exception identity and safe logging.

## Related ADRs

- [ADR-0005](0005-request-layer.md): request-carrier responsibility.
- [ADR-0012](0012-retry-strategy.md): retry ownership.
- [ADR-0013](0013-transport-base-class.md): middleware ordering.
- [ADR-0014](0014-logging.md): shared redaction.
- [ADR-0040](0040-inbound-request-id-and-error-envelope.md): inbound scope.
- [ADR-0041](0041-error-tracking-integration-and-sentry-extra.md): reporting.
