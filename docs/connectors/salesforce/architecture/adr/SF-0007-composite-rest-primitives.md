# SF-0007: Salesforce Composite REST Primitives

**Date:** 2026-05-10
**Status:** Accepted

## Context

Salesforce composite REST endpoints allow callers to bundle multiple REST
operations into one request. This reduces round trips and enables chained
request flows without forcing callers to orchestrate every call manually.

The generic Salesforce connector already exposes typed services for SObject,
query, search, bulk, utility, metadata, and lookup operations. Composite fits
the same pattern: it is a transport-level capability, not a business
workflow. The connector should therefore provide only the primitives needed to
build composite requests, while leaving orchestration decisions in the
consuming application.

## Alternatives Considered

### Option 1: Do Nothing

**Description:** Leave composite unsupported and require callers to make
multiple REST calls themselves.

**Pros:**

- No new surface area.
- No additional models or tests.

**Cons:**

- Forces repeated orchestration logic into consuming applications.
- Prevents common multi-request flows from benefiting from a single REST call.

**Why rejected:** Too much ceremony for a core Salesforce capability.

### Option 2: Add Business-Flow Helpers

**Description:** Implement convenience methods for specific business flows,
such as lead conversion or opportunity-plus-products orchestration.

**Pros:**

- Very ergonomic for a narrow set of use cases.

**Cons:**

- Couples the generic connector to specific business processes.
- Encourages policy and workflow logic to leak into the connector.

**Why rejected:** Violates the generic connector boundary.

### Option 3: Expose Only One Composite Endpoint

**Description:** Implement only `/composite` and leave `/batch` and `/tree`
for later.

**Pros:**

- Smallest initial implementation.

**Cons:**

- Leaves two common REST primitives unavailable.
- Requires multiple follow-up changes for a single capability family.

**Why rejected:** The three primitives are part of the same capability family
and should be modeled together.

## Decision

We will ship the generic composite REST primitives as first-class connector
building blocks and expose them through the facade as thin service factories.

This gives consumers the ability to compose their own flows while keeping the
connector free of business-specific orchestration.

## Rationale

Composite is a transport capability, not a domain workflow. The connector
should provide typed request and response models, sync and async parity, and
clean facade accessors, but it should not decide which Salesforce objects to
create or how to chain them for a particular business process.

That keeps the connector aligned with the rest of the Salesforce module:
services expose generic REST primitives, while consumers build the actual
integration flow in their own application context.

The selected scope also matches the implementation boundary already used for
query, search, bulk, and utility services: request orchestration lives in the
application, transport and typing live in the connector.

## Consequences

### Positive

- Enables chained REST requests without duplicating orchestration code.
- Covers parent/child create flows through `tree(...)`.
- Supports grouped request execution through `batch(...)`.
- Keeps business logic outside the generic connector.

### Negative / Tradeoffs

- Adds another public service family to document and test.
- Typed response models must account for Salesforce response variations.
- Callers still need to understand Salesforce composite semantics.

### Risks

- Consumers may try to use the composite service as a workflow engine.
  Mitigation: keep the docs and examples explicitly generic.
- The service surface could drift toward business helpers over time.
  Mitigation: keep new additions constrained to REST primitives.

## Related ADRs

- SF-0002: Salesforce facade ergonomics — exposes the composite service as a
  thin constructor.
- SF-0003: Salesforce Query Service Design — similar generic service pattern.
- SF-0005: Salesforce Bulk API 2.0 Service Design — another separate REST
  capability family.
