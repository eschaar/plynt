# ADR-0030: Generic gRPC Protocol Boundary and Scope

## Status

Accepted

## Context

Plynt's architecture already anticipates protocol namespaces beyond HTTP, and
the current roadmap identifies gRPC as the first likely next protocol. The
first concrete driver is Salesforce eventing, which depends on long-lived,
async-first streaming behavior rather than the existing request/response HTTP
shape.

Today, plynt has no core ADR that defines what belongs in a generic gRPC
layer, how gRPC should relate to the existing HTTP namespace, or where the
boundary sits between reusable protocol concerns and connector-specific
semantics.

That gap is material because a gRPC addition affects:

1. package boundaries and optional-install strategy,
1. protocol-specific execution semantics,
1. future sync and async expectations,
1. the boundary between reusable transport behavior and connector behavior.

Without an explicit ADR, the first connector implementation could either push
Salesforce CDC semantics into the core too early or overfit the core to HTTP
middleware assumptions that do not hold for gRPC.

## Decision

Plynt will treat gRPC as a sibling protocol namespace to HTTP, with a narrow,
async-first, optional-install core boundary.

1. gRPC belongs in `plynt` as its own protocol namespace, parallel to
   `plynt.http`, rather than as a connector-private transport.
1. The first supported posture for gRPC is async-first. This ADR does not
   promise a sync gRPC API or sync eventing adapter.
1. gRPC runtime dependencies must remain optional and isolated behind an extra
   such as `plynt[grpc]`.
1. The phase-1 install path for Salesforce eventing is composition of extras:
   `plynt[grpc,salesforce]`. `plynt[grpc]` remains the generic protocol
   extra, and `plynt[salesforce]` remains the connector extra.
1. The initial core gRPC layer must stay small and generic. It may define only
   protocol-level building blocks needed to support gRPC transport concerns in
   plynt.
1. Core gRPC must not define CDC, replay, ack, checkpoint, or other
   Salesforce-specific event semantics.
1. gRPC cross-cutting behavior must use a protocol-specific interceptor or
   hook model. Plynt must not assume direct reuse of the HTTP middleware
   contract from ADR-0013.
1. Reconnect handling, backpressure primitives, and subscribe-loop behavior may
   be promoted into generic gRPC abstractions later only if implementation
   evidence shows reuse beyond the first connector slice.

## Alternatives Considered

### Option A: Keep gRPC entirely inside the first connector

**Pros:**

- No new core namespace or ADR surface.
- Maximum short-term isolation.

**Cons:**

- Hides a protocol concern inside one connector.
- Weakens the optional-install and protocol-boundary model.
- Makes later reuse more disruptive.

**Why rejected:** The first use case is connector-driven, but the transport and
dependency boundary are still protocol-level concerns that belong in plynt.

### Option B: Build a broad generic eventing framework in the core first

**Pros:**

- Could reduce future extraction work.

**Cons:**

- Forces unproven abstractions into the core.
- Risks turning one connector's CDC semantics into package contracts.

**Why rejected:** Evidence does not yet justify a broad eventing abstraction.

### Option C: Reuse HTTP middleware directly for gRPC

**Pros:**

- Lower apparent implementation effort.

**Cons:**

- Assumes HTTP request/response lifecycle semantics map cleanly to gRPC.
- Constrains gRPC around the wrong protocol model.

**Why rejected:** gRPC needs protocol-specific interception points and
stream-lifecycle control.

### Option D: Promise sync and async gRPC support from the start

**Pros:**

- Symmetry with existing HTTP posture.

**Cons:**

- Expands the public promise surface before the async model is validated.
- Increases design and test scope materially.

**Why rejected:** The current roadmap is async-first for gRPC and eventing.

## Rationale

This decision keeps the core aligned with plynt's existing architectural
principles: protocol isolation, optional dependencies, and evidence-based
abstraction.

Making gRPC a sibling namespace to HTTP keeps protocol boundaries explicit and
reusable without forcing connector code to own generic transport concerns.
Keeping the layer async-first matches the operational reality of the first
known use case and avoids premature sync commitments.

The small-core rule protects package stability. It lets plynt add the minimum
generic gRPC foundation now while deferring reusable reconnect, backpressure,
and subscription behavior until there is proof that those concerns are truly
cross-connector rather than Salesforce-specific.

## Consequences

### Positive

- Plynt gains a clear protocol boundary for gRPC alongside HTTP.
- Optional dependency isolation remains consistent with the extras model.
- Phase-1 eventing installation stays explicit without creating a new
  Salesforce-specific eventing extra.
- Connector-specific event semantics stay out of the core.
- Future connector reuse remains possible without requiring connector-first
  extraction.

### Negative / Tradeoffs

- The first connector may temporarily carry behavior that later becomes generic.
- gRPC will need its own cross-cutting extension model instead of reusing the
  existing HTTP middleware contract.
- A future sync wrapper, if ever needed, will require separate design and ADR
  review.

### Risks

- The initial gRPC base may still be too narrow or too broad.

Mitigations:

1. Keep phase 1 limited to the smallest protocol-safe baseline.
1. Promote additional generic behavior only after reuse is demonstrated.
1. Use connector implementation evidence to drive follow-up ADRs.

## Related ADRs

- ADR-0002: Layered Architecture
- ADR-0003: Dependency Policy
- ADR-0006: Transport Layer
- ADR-0008: Client Layer
- ADR-0013: Transport Base Class
- ADR-0017: Streaming Response Support
- ADR-0028: Supported Environments and Extras Policy
- SF-0013: Salesforce Eventing Architecture
