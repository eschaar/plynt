# SF-0013: Salesforce Eventing Architecture

**Status:** Accepted

## Context

Salesforce Pub/Sub and Change Data Capture (CDC) introduce a long-lived,
backpressure-sensitive integration path that does not fit the existing
request/response HTTP transport shape.

The current roadmap and release-readiness plan already constrain the first
eventing slice:

- eventing is async-first
- the first transport is gRPC behind an optional extra
- Salesforce CDC semantics must not become premature core contracts
- HTTP middleware reuse cannot be assumed for gRPC

Plynth therefore needs a narrow eventing baseline that preserves package
boundaries, keeps the core reusable, and avoids locking in abstractions before
there is evidence from a real connector implementation.

## Decision

Adopt a phased Salesforce eventing architecture with a small generic async
gRPC base in `plynth` and connector-scoped Salesforce event semantics in phase
1\.

Phase 1 boundaries:

1. Add a minimal async gRPC foundation under an optional extra such as
   `plynth[grpc]`.
1. Use `plynth[grpc,salesforce]` as the canonical phase-1 install path.
   `plynth[grpc]` remains the generic protocol extra, and
   `plynth[salesforce]` remains the connector extra.
1. Keep subscribe-loop behavior, reconnect flow, and backpressure handling only
   as generic as required to support one working async streaming path.
1. Keep Salesforce-specific semantics in
   `plynth.connectors.salesforce`, including CDC envelope mapping, replay or
   checkpoint semantics, and subscription-facing behavior.
1. Keep Salesforce eventing implementation in this package generic across
   Salesforce orgs and instances.
1. Do not add tenant-, customer-, or instance-specific business rules,
   mappings, or hardcoded assumptions to the generic CDC package surface.
1. Place tenant-, customer-, or instance-specific behavior outside this
   package boundary, for example in consumer-layer or
   integration-specific adapters.
1. Keep ack internal to the Salesforce connector in phase 1 rather than part
   of the public package-level subscription contract.
1. Do not assume direct reuse of HTTP middleware. If cross-cutting protocol
   concerns are needed, model them through gRPC-specific interceptors or hooks.
1. Do not promise a sync eventing API in this phase.

Phase 1 delivery semantics:

1. Delivery is explicitly at-least-once. Consumers must handle duplicates
   through idempotent processing.
1. Reconnect is automatic but bounded. Resume from the last accepted replay or
   checkpoint position when available; otherwise fail clearly.
1. Ordering is preserved only within a live subscription segment. Phase 1 does
   not promise gap-free global ordering across reconnect or replay boundaries.

Phase 2 guardrail:

1. Promote reconnect, backpressure, or subscribe-loop behavior into a more
   generic protocol layer only after implementation evidence shows reuse beyond
   the Salesforce connector.
1. Consider moving Avro handling into a generic layer only when implementation
   evidence shows non-Salesforce reuse and clear net reduction in connector
   complexity.

## Alternatives Considered

1. Build a broad generic eventing framework before the first connector.
   Rejected because it would force unproven abstractions into the core.
1. Keep all gRPC and streaming behavior fully inside the Salesforce connector.
   Rejected because phase 1 still benefits from a small reusable async gRPC
   base and optional-install boundary in `plynth`.
1. Reuse HTTP middleware directly for gRPC eventing.
   Rejected because transport lifecycle, metadata flow, and streaming control
   differ enough that reuse would be assumption-driven rather than evidence-
   driven.
1. Offer sync and async eventing from the start.
   Rejected because it would widen the promise surface before the async model
   is proven.

## Rationale

This decision keeps the first implementation aligned with the roadmap while
protecting core package stability.

- Async-first matches the operational shape of Salesforce Pub/Sub and CDC.
- An optional gRPC extra preserves the modular install model.
- The phase-1 install surface stays explicit through extra composition rather
  than a new eventing-specific package extra.
- Connector-scoped semantics avoid hard-coding Salesforce replay and CDC rules
  into the core too early.
- Evidence-based extraction reduces the risk of freezing the wrong generic
  abstraction.
- A protocol-specific interceptor or hook model preserves room for auth,
  logging, metrics, and resilience concerns without forcing HTTP assumptions
  onto gRPC.

## Consequences

Positive:

- Plynth gains a minimal eventing path without broad new core contracts.
- Salesforce CDC can move forward behind a clear async-only boundary.
- Optional-install and extraction strategy remain consistent with existing ADRs.
- The phase-1 public install path is unambiguous: `plynth[grpc,salesforce]`.
- The CDC connector surface remains reusable across orgs and instances.

Negative:

- Some duplication may remain in the Salesforce connector until reuse is
  proven.
- A future second eventing connector may require follow-up ADR work before
  shared abstractions are promoted.
- Middleware-style cross-cutting behavior for gRPC will need its own focused
  shape instead of piggybacking on HTTP middleware.
- Tenant- or customer-specific rules require a separate consumer or
  integration adapter layer.

## Related ADRs

- [ADR-0030](../../../../architecture/adr/0030-grpc-protocol-boundary.md) —
  Generic gRPC Protocol Boundary and Scope
- [SF-0012](sf-0012-extraction-strategy.md) — Salesforce Integration
  Extraction
- [ADR-0013](../../../../architecture/adr/0013-transport-base-class.md) —
  Transport Base Class

## Addendum (2026-09-10): Vendored Pub/Sub stub

Decision: vendor Salesforce's `eventbus.v1` (`pubsub_api.proto`) generated
stub inside `plynth.connectors.salesforce.cdc._proto`, rather than requiring
every caller to generate their own stub.

Rationale:

1. `pubsub_api.proto` is identical across all Salesforce orgs — it is not
   tenant- or instance-specific, so it fits the existing "generic across
   orgs" CDC boundary rather than something that must stay caller-supplied.
1. No new runtime dependency: `grpcio` and `protobuf` are already accepted
   under the `grpc` extra. Vendoring only adds a dev-time codegen dependency
   (`grpcio-tools`) and committed generated output.
1. The upstream proto is stable (single-digit changes over several years) and
   CC0-1.0 licensed, so redistribution and low-frequency drift-checking are
   both low-risk and low-maintenance.
1. `GrpcStubPubSubAdapter` (caller-supplied stub) remains available and
   unchanged for callers who need a custom-generated stub; the vendored path
   is additive via `create_vendored_pubsub_adapter(channel)`, not a breaking
   change to existing constructors.

This stays scoped to `plynth.connectors.salesforce.cdc` per SF-0013's
existing boundary — it is not promoted to a sibling package or to
`plynth.grpc`, since CDC subscribe/GetSchema remains the only consumer.
Regeneration is a deliberate, reviewed action
(`make salesforce-cdc-proto-generate`), never an automatic build or CI step.
See `src/plynth/connectors/salesforce/cdc/_proto/README.md` and `SOURCE.md`
for provenance and regeneration instructions.
