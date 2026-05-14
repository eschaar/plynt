# ADR-0022: Upstream Rate Governance

## Status

Proposed

## Context

Plynth already provides local rate limiting through the core middleware layer.
That covers fixed client-side request shaping, but it does not define
governance behavior for upstream quota and throttling signals.

Many APIs return throttling hints such as status codes, reset windows, and
retry delays. Without shared governance semantics, connectors may implement
different handling for the same signals. This leads to inconsistent behavior
under load and makes reliability tuning difficult.

The governance model must stay connector-agnostic and reusable across service
domains. Provider-specific header names and quota details remain adapter-level
concerns.

## Decision

Define a core upstream rate governance policy that standardizes throttling
behavior across connectors.

### 1. Governance inputs

The policy consumes normalized upstream throttle signals:

- throttle status
- retry delay
- reset timestamp
- remaining quota and limit values when available

Normalization from provider-specific headers into these fields is performed by
connectors or client adapters.

### 2. Governance actions

The policy supports three explicit actions:

- delay: wait before next attempt
- reject: fail fast with a typed governance exception
- proceed: allow request execution

Action selection must be deterministic for the same input signals and policy
configuration.

### 3. Retry integration

Retry behavior must consume governance output instead of bypassing it.
When governance emits a delay, retry logic uses that delay as the minimum wait
time. When governance emits reject, retry must stop.

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

Rate governance is a cross-cutting reliability concern, not domain logic.
Putting the decision policy in core middleware yields consistent behavior and
keeps connector implementations focused on protocol and payload mapping.

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

1. A core governance policy type exists with deterministic action outputs.
1. A normalized throttle signal model exists and is connector-agnostic.
1. Retry integration honors governance delay and reject outputs.
1. Sync and async governance behaviors are parity-tested.
1. Connector tests validate normalization from provider-specific signals.
1. Governance exceptions are typed and mapped consistently in error handling.

## Related ADRs

- ADR-0003: Dependency Policy
- ADR-0012: Retry Strategy
- ADR-0019: Circuit Breaker Middleware
- ADR-0020: Rate Limit Middleware
