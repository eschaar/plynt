# ADR-0022: Throttle Governance

## Status

Accepted

## Context

Plynt already provides local rate limiting through the core middleware layer.
That covers fixed client-side request shaping, but it does not define
governance behavior for upstream quota and throttling signals.

Many APIs return throttling hints such as status codes, reset windows, and
retry delays. Without shared governance semantics, connectors may implement
different handling for the same signals. This leads to inconsistent behavior
under load and makes reliability tuning difficult.

The governance model must stay connector-agnostic and reusable across all
service domains. Plynt is a client library for consuming external APIs, not
an API provider; governance is therefore upstream-facing only.
Provider-specific header names and quota details remain adapter-level concerns.

## Decision

Define a core throttle governance policy that standardizes throttling behavior
across connectors. The policy works with normalized throttle signals that are
produced by connectors or client adapters from provider-specific headers and
response metadata.

### 1. Governance inputs

The policy consumes normalized throttle signals:

- throttle status (detected / not detected)
- retry delay
- reset timestamp
- remaining quota and limit values when available

Normalization from provider-specific headers and response codes into these
fields is performed by connectors or client adapters.

### 2. Governance actions

The policy supports three explicit actions:

- delay: wait before next attempt
- reject: fail fast with a typed governance exception
- proceed: allow request execution

Action selection must be deterministic for the same input signals and policy
configuration.

### 3. Retry integration

Retry behavior must consume governance output instead of bypassing it.
When governance emits a delay, retry logic uses `max(backoff_delay, governance_delay)` as
the next wait time. This ensures governance delay takes precedence if it is
longer than the retry backoff. When governance emits reject, retry must stop
immediately.

### 4. Circuit-breaker integration

Governance decisions must remain independent from circuit-breaker state while
preserving chain order. Circuit-breaker and governance each keep one
responsibility:

- circuit breaker handles dependency health state
- governance handles quota and throttling state

### 5. Sync and async parity

Sync and async middleware paths must apply the same governance rules and
produce equivalent outcomes for the same request sequence.

### 6. State scope

Default state scope remains process-local per middleware instance. Shared
cross-process state is out of scope for this ADR and may be added through a
separate extension contract.

## Alternatives Considered

### Option A: Keep governance in each connector

**Description:** Let every connector implement its own upstream throttling
behavior.

**Pros:**

- Fast local implementation.
- Full per-connector flexibility.

**Cons:**

- Semantic drift across connectors.
- Higher maintenance and debugging cost.
- No reusable reliability baseline.

**Why rejected:** The same governance problem would be solved repeatedly.

### Option B: Centralize governance in core middleware

**Description:** Define one shared policy with normalized inputs and actions.

**Pros:**

- Consistent behavior across connectors.
- Lower operational complexity.
- Easier parity testing and observability.

**Cons:**

- Requires adapter normalization work per connector.
- Some provider nuance stays outside core behavior.

**Why chosen:** It gives consistency while preserving connector boundaries.

## Rationale

Throttle governance is a cross-cutting reliability concern, not domain logic.
Putting the decision policy in core middleware yields consistent behavior and
keeps connector implementations focused on protocol and payload mapping.
Using straightforward naming (ThrottleSignal, ThrottleGovernancePolicy) rather
than "upstream"-prefixed names keeps the API concise and readable, since
plynt's only perspective is upstream (consuming external APIs).

## Consequences

### Positive

- Consistent throttle handling semantics across connectors.
- Cleaner separation between provider normalization and policy decisions.
- Better predictability under burst traffic.

### Negative / Tradeoffs

- Connectors must implement and maintain signal normalization.
- Some advanced quota strategies remain outside the initial scope.

### Risks

- Incorrect normalization can produce wrong policy decisions.
- Delay behavior may increase tail latency under sustained throttling.

Mitigations:

- Add connector conformance tests for normalization.
- Add shared governance test vectors for sync and async paths.
- Expose governance decisions through structured debug telemetry.

## Acceptance Criteria

1. ✅ A core `ThrottleGovernancePolicy` type exists with deterministic action outputs.
1. ✅ A normalized `ThrottleSignal` model exists and is connector-agnostic.
   `reset_at_seconds` (from `X-RateLimit-Reset`) is extracted by the middleware
   and honoured as a fallback delay source in `evaluate()`.
1. ✅ `ThrottleGovernanceMiddleware` (sync and async) in `plynt.middleware.throttle`
   apply policy and raise typed exceptions.
1. ✅ Retry integration honors governance delay and reject outputs via
   `max(backoff, governance_delay)`.
1. ✅ Sync and async governance behaviors are parity-tested.
1. ✅ Connector tests validate normalization from provider-specific signals.
   The Salesforce connector exposes `_salesforce_quota_signal` to normalize
   `Sforce-Limit-Info: api-usage=X/Y` quota exhaustion into a `ThrottleSignal`.
   Tests in `tests/connectors/salesforce/test_throttle.py` cover both this
   Salesforce-specific helper and `_extract_throttle_signal` with Salesforce
   response shapes (429 `REQUEST_LIMIT_EXCEEDED`, 503 with `Retry-After`).
1. ✅ Governance exceptions are typed and mapped consistently in error handling.

## Related ADRs

- ADR-0003: Dependency Policy
- ADR-0012: Retry Strategy
- ADR-0019: Circuit Breaker Middleware
- ADR-0020: Rate Limit Middleware
