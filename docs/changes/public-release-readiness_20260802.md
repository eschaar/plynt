# Public Release Readiness Plan

status: BUILD
type: roadmap
reference: ROADMAP-PUBLIC-READINESS
date: 2026-08-02
last_modified: 2026-08-02
owner: TBD

## Goal and Context

Prepare plynth as a public package with clear API contracts, predictable
versioning, release gates, and operational expectations. Salesforce eventing is
an important workstream in this release track, but it is one part of package
readiness rather than the primary scope.

## AS-IS / TO-BE

AS-IS

1. Core abstractions and connectors exist, but public support boundaries are
   not fully documented.
1. Compatibility, deprecation, and release policy are not yet complete as a
   package-level contract.
1. Quality gates exist in parts, but go/no-go criteria are not unified.
1. Salesforce eventing implementation is not yet built, but its phase-1
   boundary is now locked by accepted ADRs.

TO-BE

1. Plynth has a public-ready package baseline with explicit compatibility,
   support, and deprecation rules.
1. Release acceptance is driven by a single readiness checklist and evidence.
1. Documentation and examples align with supported installation extras and
   usage patterns.
1. Salesforce eventing has an accepted, phased architecture compatible with
   package-level stability goals.

Phase-1 implementation slice added here

1. Generic Salesforce CDC models now live in `src/plynth/connectors/salesforce/cdc/models.py`.
1. The async CDC subscriber contract and subscribe orchestration now live in
   `src/plynth/connectors/salesforce/cdc/service.py`.
1. The Salesforce connector package exports the CDC surface from `src/plynth/connectors/salesforce/__init__.py`.
1. Shadow-store consumers remain out of package and out of connector scope.
1. No tenant-, customer-, or instance-specific CDC logic is introduced in the generic CDC package boundary.
1. The phase-1 envelope is aligned to the generic Salesforce CDC/Pub/Sub
   message shape, including replay metadata and commit context.
1. The CDC slice now models Salesforce Pub/Sub auth metadata and a
   Quick-Start-aligned subscribe flow with schema fetch and injected payload
   decoding.
1. Shadow-store materialization remains external and is not implemented in
   plynth or the Salesforce connector.

## Scope In / Out

In scope

1. Package-first release readiness for core, adapters, and public docs.
1. Public API boundary definition and backward-compatibility policy.
1. Test, CI, and observability gates needed for public release confidence.
1. Salesforce eventing architecture and first implementation slice.

Out of scope

1. Connector redesigns unrelated to public release readiness.
1. Multi-cloud event broker strategy beyond current package objectives.
1. Large refactors outside release-critical quality or API consistency.
1. Marketing, pricing, or commercial launch operations.

## Milestones 30/60/90

Day 0-30

1. Approve package-level ADRs for compatibility, versioning, and release gates.
1. Freeze minimum supported Python/runtime matrix and extras policy.
1. Baseline public docs and examples for supported usage paths.
1. Finalize Salesforce eventing decision criteria and spike plan.

Day 31-60

1. Implement highest-priority readiness gaps in API contracts and tests.
1. Establish a release checklist with measurable pass/fail evidence.
1. Deliver first Salesforce eventing slice behind stable interfaces.
1. Run package-level readiness review and close top blockers.

Day 61-90

1. Complete compatibility validation across supported environments.
1. Harden observability and failure-mode behavior for release-critical flows.
1. Finalize migration notes and deprecation guidance.
1. Approve public release go/no-go on objective readiness criteria.

## First Steps (1-2 Weeks)

- [x] Draft ADR: package compatibility, deprecation, and support policy.
- [x] Create a public-release checklist with owners and evidence sources.
- [x] Gap-assess docs and examples against intended public API surfaces.
- [x] Define and start contract-test coverage for critical public interfaces.
- [x] Run Salesforce eventing spike planning with async-first decision
  hypotheses and rollback assumptions.

## Salesforce Eventing Spike Plan

Spike goal

Define the smallest package-safe path to add Salesforce eventing as a
capability workstream in plynth without weakening existing sync/async
principles, public API stability, or optional-install boundaries.

Async-first framing

1. Treat Salesforce eventing as async-first because Pub/Sub and CDC delivery
   are long-lived, backpressure-sensitive flows.
1. Reuse core request, response, error, and settings patterns where they fit,
   but do not force HTTP-shaped assumptions onto event consumption.
1. Do not assume existing HTTP middleware can be reused directly for gRPC.
   Similar concerns may still exist at the protocol layer, including
   auth/metadata injection, logging and metrics hooks, and retry or reconnect
   governance.
1. A protocol-specific middleware or interceptor model may be appropriate for
   gRPC, separate from HTTP middleware.
1. Keep any sync eventing adapter explicitly out of the current promise set.
   If needed later, it must wrap an already-proven async core rather than
   define the baseline architecture.

Hypotheses to test

1. A small generic async gRPC base in plynth can support eventing behind an
   optional extra without turning CDC semantics into immediate core contracts.
1. Salesforce event payload handling can reuse neutral core models and error
   conventions while keeping transport-specific streaming concerns in an
   adapter layer.
1. Ack, replay, and CDC semantics should stay in the Salesforce connector
   first, while generic concerns are promoted into a core or protocol layer
   only after evidence shows they are reusable.
1. Ack, replay, and reconnect behavior can be exposed through a narrow,
   package-stable interface that does not leak raw gRPC implementation detail.
1. Event schema evolution and idempotency rules can be defined at the package
   boundary before any sync adapter or second broker is considered.

Scope

1. Evaluate one async-first architecture for Salesforce Pub/Sub and CDC as a
   plynth capability workstream.
1. Identify the minimum abstractions, optional extra boundary, and ADR topics
   required before implementation.
1. Prove or reject a first implementation slice focused on subscribe,
   checkpoint/replay handling, and typed event envelope mapping.

Current slice status

1. Implemented: typed generic subscribe request and CDC event envelope.
1. Implemented: async placeholder subscriber contract with a clear not-yet-implemented error.
1. Deferred: checkpoint/replay storage, transport wiring, and shadow-store consumer implementation.
1. Deferred: any tenant-, customer-, or instance-specific CDC behavior.

Non-goals

1. Do not implement production eventing code in this spike.
1. Do not promise sync event consumption, multi-broker portability, or package
   extraction in this session.
1. Do not redesign unrelated Salesforce REST, Bulk, AI, or framework adapter
   surfaces.
1. Do not place tenant-, customer-, or instance-specific CDC business logic,
   mappings, or hardcoded assumptions inside the generic Salesforce CDC
   package boundary.

Success criteria

1. One recommended async-first architecture is documented with explicit fit to
   plynth package boundaries.
1. The spike ends with a go or no-go recommendation for a first eventing ADR
   and implementation slice.
1. Required rollback assumptions are explicit: if the transport abstraction is
   too leaky, eventing remains limited to the Salesforce slice behind an extra,
   with only the minimal generic gRPC base retained.
1. Open questions are reduced to a short ADR input list rather than broad
   architectural uncertainty.

Failure criteria

1. The spike cannot identify a stable public boundary without exposing raw
   transport internals.
1. The spike requires a new core dependency or core abstraction change without
   prior ADR support.
1. Replay, ordering, or idempotency expectations cannot be stated clearly
   enough to support package-level contracts.
1. The only viable design would duplicate sync and async business logic.

Expected outputs

1. A short spike note in `docs/changes/` or folded into this plan with the
   recommended direction and rejected alternatives.
1. A proposed ADR outline for Salesforce eventing transport strategy.
1. A first implementation slice proposal covering package location, optional
   extra, failure modes, and validation approach.
1. A decision on whether to proceed, defer, or narrow scope further.

Owners and roles

| Role         | Responsibility                                                                          |
| ------------ | --------------------------------------------------------------------------------------- |
| Architecture | Confirm package boundary, async-first direction, and ADR inputs                         |
| Engineering  | Validate technical feasibility against existing transport and connector patterns        |
| Product      | Confirm that eventing remains one capability workstream within public release readiness |
| QA           | Define the minimum validation evidence for the first implementation slice               |

Recommended sequence for next session

1. Re-read roadmap direction in `docs/product/roadmap.md` and this plan to
   keep the async-first scope fixed.
1. Inspect current Salesforce connector boundaries and list candidate locations
   for eventing code without changing core abstractions.
1. Compare only the agreed phase-1 shape against any broader alternative:
   small generic async gRPC base plus connector-scoped CDC semantics versus a
   wider eventing abstraction that would require ADR escalation.
1. Record findings, choose one recommendation, and draft the eventing ADR
   inputs: boundary, optional extra, failure modes, replay model, and
   observability needs.
1. Stop if the preferred option requires a new core dependency or core
   abstraction change, and escalate that decision before implementation.

## Public Release Checklist (Owners and Evidence)

| Gate                                             | Owner           | Evidence Source                                                                                                                              | Status |
| ------------------------------------------------ | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| API compatibility/deprecation policy adopted     | Architecture    | `docs/architecture/adr/0027-public-api-compatibility-and-deprecation-policy.md`                                                              | Done   |
| Linux tox matrix pass (3.11/3.12/3.13/3.14)      | Engineering     | `tox -e py311,py312,py313,py314` CI run and logs                                                                                             | Done   |
| Release gate evidence artifact available         | Release Manager | `docs/releases/` artifact for release date                                                                                                   | Done   |
| Public docs baseline complete                    | Docs            | `README.md`, `README-pypi.md`, `examples/*/README.md` review notes                                                                           | Done   |
| Critical public interface contract tests passing | Engineering     | `tests/base/test_base_package.py`, `tests/http/test_http_package.py`, `tests/connectors/salesforce/test_salesforce_package.py` pytest output | Done   |
| Security/dependency checks passing               | Security        | `make check`, dependency scan, and lockfile audit output                                                                                     | Done   |

## Docs and Examples Gap Assessment (2026-08-02)

Reviewed sources

- `README.md`
- `README-pypi.md`
- `examples/django/README.md`
- `examples/drf/README.md`
- `examples/llm/README.md`
- `examples/salesforce/README.md`

Implemented updates

- Added one canonical extras matrix in `README.md` and mirrored it in
  `README-pypi.md` for supported extras: `httpx`, `django`, `drf`,
  `fastapi`, `salesforce`.
- Added a concise public API surface summary in `README.md` and
  `README-pypi.md` with emphasis on package exports in `plynth.base` and
  `plynth.http`, including ADR reference to
  `docs/architecture/adr/0027-public-api-compatibility-and-deprecation-policy.md`.
- Normalized `Prerequisites` and added a short `Validation checklist` section
  across `examples/django/README.md`, `examples/drf/README.md`,
  `examples/llm/README.md`, and `examples/salesforce/README.md`.

Checklist note

- This checklist remains in this plan file as a temporary artifact for steps 1-4.

## Success Criteria

1. Public package contract is approved and documented.
1. Release checklist is complete and all blocking criteria pass.
1. Compatibility and contract tests cover critical public surfaces.
1. Salesforce eventing path is ADR-approved and aligned to package stability.
1. Go/no-go decision uses measured evidence, not implicit assumptions.

## NFR Placeholders

1. Package-level backward compatibility pass rate: TBD %.
1. Critical workflow reliability over 30 days: TBD %.
1. Public API docs accuracy against implementation: TBD %.
1. CI gate stability (flake/failure threshold): TBD %.
1. Eventing p95 latency and recovery objectives: TBD.

## Risks and Dependencies

1. Unclear ownership for package compatibility policy may delay decisions.
1. Test matrix expansion can increase CI cost and cycle time.
1. Salesforce platform constraints may narrow eventing transport options.
1. Documentation lag may block public confidence even if code is ready.
1. Late API changes can invalidate early readiness evidence.

## ADRs to Create First

1. ADR: Public API compatibility and deprecation policy.
1. ADR: Supported environments and optional extras policy.
1. ADR: Release acceptance gates and evidence model.
1. ADR: Salesforce eventing architecture (phased transport strategy).
1. ADR: Event schema evolution and idempotency expectations.

## Roadmap Decision: Sync, Async, and Eventing

This direction is now captured in the durable product roadmap in
`docs/product/roadmap.md`.

- Preserve sync and async support as a standing architectural principle.
- Deliver roadmap phases by capability rather than by one global transport cut.
- Keep HTTP capabilities on a sync/async parity path where those surfaces are
  already stable.
- Treat gRPC and Salesforce eventing as async-first in the current roadmap.
- Evaluate sync eventing later as a follow-up decision, not as a current
  delivery promise.

## Salesforce Eventing Decision Points

Preferred option

1. Choose a phased direction: phase 1 is a small generic async gRPC base in
   plynth plus connector-scoped Salesforce CDC semantics.
1. Keep the first CDC slice inside `plynth.connectors.salesforce`, installed
   via `plynth[grpc,salesforce]`, with no broader eventing core contract unless
   a dedicated ADR later promotes proven generic behavior.
1. Promote only validated generic concerns into a core or protocol layer after
   evidence shows reuse beyond the CDC slice.

Rejected option

1. Do not start with a broad public eventing abstraction first.
1. A transport-first phase beyond the minimal gRPC base would widen scope
   before package value is proven, front-load ADR and dependency work, and
   risk forcing core contracts around one connector use case too early.

ADR inputs

1. Package boundary: minimal generic gRPC base now, connector-scoped CDC
   semantics first, and later extraction only when reuse is proven.
1. Optional extra and dependency plan for Salesforce eventing and any gRPC
   runtime.
1. Public interface shape for subscribe, replay/checkpoint, ack, and shutdown.
1. Failure model for reconnect, backpressure, duplicate delivery, ordering,
   and schema resolution failures.
1. Extraction candidates to validate in the CDC slice: reconnect lifecycle
   patterns, backpressure handling primitives, and subscribe loop base
   behavior.
1. Middleware model for gRPC: separate protocol-specific interceptors or hooks
   rather than assumed reuse of HTTP middleware.
1. Observability contract: logs, metrics, and evidence needed for release
   gates.
1. Sync posture: async-first now, with any future sync wrapper explicitly out
   of the initial ADR scope.

First implementation slice recommendation

1. Phase 1: deliver a small generic async gRPC base plus one async subscribe
   loop for Salesforce CDC with typed event envelope mapping,
   replay/checkpoint input, reconnect handling, and contract tests behind a
   non-core extra.
1. Keep schema registry and consumer ergonomics minimal until the package
   boundary proves stable.
1. Phase 2: extract only the eventing parts proven generic by the CDC slice,
   such as reconnect lifecycle patterns, backpressure primitives, and
   subscribe loop base behavior.
1. Do not publish those extracted parts as stable core contracts until the CDC
   slice validates that they are genuinely reusable.

Escalation triggers

1. A new core ADR is required before implementation if eventing needs a new
   runtime dependency outside a connector extra.
1. A new core ADR is required if eventing cannot fit connector scope without a
   minimal reusable `grpc/` namespace, new base abstractions beyond that, or
   changes to sync/async transport contracts.
1. A new core ADR is required if public eventing semantics must become shared
   across connectors rather than Salesforce-specific.

## ADR Acceptance Outcome

## Accepted Decisions

1. Packaging split between generic gRPC and Salesforce eventing installs

   - Accepted decision: keep `plynth[grpc]` as the small generic async gRPC
     transport extra, keep `plynth[salesforce]` as the connector extra, and
     use `plynth[grpc,salesforce]` as the phase-1 eventing install surface.
   - Short rationale: this keeps the package-first boundary explicit without
     adding a new eventing-specific extra. The generic gRPC base stays
     reusable and small, while Salesforce eventing remains the first
     connector-scoped semantic surface.
   - Impact on ADR-0030 or SF-0013: ADR-0030 treats `plynth[grpc]` as
     protocol-only scope. SF-0013 treats `plynth[grpc,salesforce]` as the
     canonical phase-1 install path.

1. Ack in the first public subscription contract

   - Accepted decision: do not include ack in the first public subscription
     contract. Keep ack internal to the Salesforce connector in phase 1, and
     expose replay or checkpoint input plus shutdown and error handling as the
     public control surface.
   - Short rationale: ack is the most connector-shaped semantic in the first
     slice. Exposing it now would widen the public contract before there is
     reuse evidence beyond Salesforce.
   - Impact on ADR-0030 or SF-0013: ADR-0030 remains clean because ack stays
     out of the generic gRPC boundary. SF-0013 should state that ack is a
     phase-1 connector implementation detail, not a package-level contract.

1. Duplicate delivery posture

   - Accepted decision: phase 1 is explicitly at-least-once. Duplicate
     delivery is expected across reconnect, replay, and recovery paths, and
     consumers must treat event handling as idempotent.
   - Short rationale: this is the practical and honest contract for the first
     async eventing slice. It avoids an unprovable exactly-once promise while
     still giving callers a stable recovery model.
   - Impact on ADR-0030 or SF-0013: ADR-0030 does not need duplicate-delivery
     semantics in core scope. SF-0013 should make at-least-once delivery and
     consumer idempotency an explicit part of the connector contract.

1. Ordering and reconnect posture

   - Accepted decision: preserve stream ordering only within a live
     subscription segment as delivered by Salesforce. After reconnect or
     replay, do not promise a gap-free global ordering guarantee. Reconnect
     should be automatic and bounded, with resume from the last accepted
     replay or checkpoint position when available; otherwise fail clearly.
   - Short rationale: this keeps the contract implementable and aligned with
     the first async-first slice. It gives a clear recovery posture without
     claiming stronger ordering guarantees than the transport can sustain.
   - Impact on ADR-0030 or SF-0013: ADR-0030 can continue to treat reconnect
     lifecycle as a candidate for later generic promotion. SF-0013 should lock
     phase-1 ordering and reconnect semantics at this level and no stronger.

### ADR-0030 Acceptance Checklist

- Confirm the phase-1 namespace and packaging boundary: generic gRPC lives in
  `plynth` under its own sibling protocol namespace, with runtime dependencies
  isolated behind `plynth[grpc]`.
- Confirm that phase 1 stays async-first only and does not imply a sync gRPC
  or sync eventing promise.
- Confirm that Salesforce semantics remain out of core scope: no CDC,
  replay, ack, or checkpoint contracts in generic gRPC.
- Confirm that reconnect, backpressure, and subscribe-loop behavior are
  promotable only after reuse evidence beyond the first connector slice.

Accepted baseline

- Treat `plynth[grpc]` as the protocol-only extra, `plynth[salesforce]` as the
  connector extra, and `plynth[grpc,salesforce]` as the phase-1 eventing
  install surface.
- Keep gRPC interceptor or hook shape as follow-up design work, not an
  acceptance blocker for ADR-0030.

Status

- Accepted on this baseline.

### SF-0013 Acceptance Checklist

- Confirm that SF-0013 depends on ADR-0030 and inherits its async-first,
  sibling-namespace, optional-install constraints.
- Confirm the connector boundary for phase 1: CDC envelope mapping,
  replay/checkpoint semantics, and subscription-facing behavior stay in
  `plynth.connectors.salesforce`.
- Confirm the intended public contract surface for phase 1 at a decision
  level: subscribe lifecycle, shutdown, replay/checkpoint input, and ack
  remains connector-specific rather than part of the exposed interface.
- Confirm the minimum failure-mode contract to support release readiness:
  reconnect behavior, duplicate delivery expectations, ordering posture,
  backpressure handling, and schema-resolution failure handling.
- Confirm the minimum observability contract and release evidence for the first
  eventing slice: logs, metrics, and contract-test expectations.

Accepted baseline

- Use the composed install surface `plynth[grpc,salesforce]` for the phase-1
  connector contract, while preserving `plynth[grpc]` and
  `plynth[salesforce]` as the underlying generic and connector extras.
- Keep ack internal in phase 1.
- Make phase 1 explicitly at-least-once, require consumer idempotency, preserve
  ordering only within a live subscription segment, and use bounded automatic
  reconnect with replay or checkpoint resume when available.

Status

- Accepted on this baseline.

### Accepted Sequence

1. ADR-0030 was accepted first on the packaging and boundary baseline.
1. SF-0013 was accepted second, immediately after, on the same baseline for
   phase-1 contract and failure-mode semantics.

## Phase-1 Implementation Design Slice

### Proposed package and module layout

1. `src/plynth/grpc/__init__.py`: export `AsyncGrpcClient`,
   `GrpcClientSettings`, and `GrpcInterceptor`.
1. `src/plynth/grpc/client.py`: own async channel setup, stream startup,
   shutdown, and bounded reconnect without CDC semantics.
1. `src/plynth/grpc/settings.py`: hold target, TLS, timeout, metadata, and
   reconnect settings.
1. `src/plynth/grpc/errors.py`: define generic connect, stream, and
   reconnect-exhausted errors.
1. `src/plynth/grpc/interceptor.py`: define async lifecycle hook protocols and
   context objects.
1. `src/plynth/connectors/salesforce/cdc/__init__.py`: export
   `AsyncSalesforceCDCSubscriber`, `SalesforceCDCSubscribeRequest`, and
   `SalesforceCDCEvent`.
1. `src/plynth/connectors/salesforce/cdc/service.py`: expose the public async
   subscribe surface for phase 1.
1. `src/plynth/connectors/salesforce/cdc/models.py`: hold typed CDC event,
   replay input, and cursor models.
1. Keep Salesforce CDC implementation in this package generic across orgs and
   instances. Put tenant-, customer-, or instance-specific behavior in
   consumer or integration-specific adapters outside this package boundary.
1. `src/plynth/connectors/salesforce/cdc/settings.py`: hold the minimal
   CDC config layered on existing Salesforce auth settings.
1. `src/plynth/connectors/salesforce/cdc/_mapping.py`,
   `src/plynth/connectors/salesforce/cdc/_subscribe.py`, and
   `src/plynth/connectors/salesforce/cdc/_ack.py`: keep protobuf decode,
   subscribe-loop state, and ack dispatch internal in phase 1.

### Primary public entry points for phase 1

1. `plynth.grpc.AsyncGrpcClient`: minimal async-first transport entry point for
   connector-owned gRPC stubs and streams.
1. `plynth.grpc.GrpcClientSettings`: stable config object for endpoint, TLS,
   metadata, timeout, and bounded reconnect behavior.
1. `plynth.connectors.salesforce.cdc.AsyncSalesforceCDCSubscriber`:
   connector entry point that exposes `subscribe(request)` as an async iterator
   of typed CDC events.
1. `plynth.connectors.salesforce.cdc.SalesforceCDCSubscribeRequest`:
   public request object carrying topic name, replay input, and flow-control
   options.
1. `plynth.connectors.salesforce.cdc.SalesforceCDCEvent`: typed phase-1
   event envelope returned to consumers.

### Internal-only pieces for phase 1

1. Generic gRPC channel factory, metadata merge, retry budget, and stream-pump
   loop stay internal to `plynth.grpc`.
1. Salesforce subscribe request translation, protobuf decode, schema lookup,
   replay cursor normalization, and ack batching stay internal to the
   Salesforce connector.
1. Ack remains connector-internal and must not be exported as a public package
   contract in this slice.

### Interceptor and hook shape at a high level

1. Use async lifecycle hooks rather than HTTP middleware reuse:
   `before_connect`, `after_connect`, `before_subscribe`, `after_message`,
   `on_error`, and `on_close`.
1. Hook context should carry target, RPC method, attempt number, metadata, and
   an opaque connector context object.
1. Hooks may observe, append metadata, and emit metrics or logs. They must not
   own CDC replay, ack, or envelope semantics.

### Minimal settings and config shape

| Surface                         | Minimal phase-1 fields                                                                                                                                   |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GrpcClientSettings`            | `target`, `tls`, `connect_timeout`, `stream_timeout`, `default_metadata`, `reconnect_max_attempts`, `reconnect_backoff_initial`, `reconnect_backoff_max` |
| `SalesforceEventingSettings`    | `pubsub_endpoint`, `max_inflight_events`, `schema_fetch_timeout`, plus reuse of existing Salesforce auth settings for credentials                        |
| `SalesforceCDCSubscribeRequest` | `topic_name`, `replay_preset` or `replay_from`, and optional batch or flow-control hints                                                                 |

### Contract test targets

1. `tests/grpc/test_client.py`: interceptor order, metadata
   propagation, graceful close, and bounded reconnect stop conditions.
1. `tests/grpc/test_settings.py`: stable settings defaults and config
   validation for the public gRPC surface.
1. `tests/connectors/salesforce/cdc/test_service.py`:
   typed envelope mapping, replay resume input, at-least-once duplicate
   posture, bounded reconnect behavior, and no public ack surface.
1. `tests/connectors/salesforce/cdc/test_cdc_ordering_contract.py`:
   ordering only within a live subscription segment and explicit no-promise
   across reconnect boundaries.

### First implementation order

1. Add the `plynth.grpc` package skeleton with exports, settings, errors, and
   interceptor protocols.
1. Implement the minimal async stream client with fake-stream contract tests
   for connect, subscribe, reconnect budget, and close behavior.
1. Add the Salesforce eventing package with CDC request or event models,
   internal mapping, and a first async subscribe loop.
1. Add Salesforce contract tests for replay input, duplicate delivery posture,
   ordering within a live segment, and bounded reconnect failure behavior.

### Explicit non-goals for the first coding slice

1. No sync gRPC API and no sync CDC adapter.
1. No generic event bus, broker abstraction, or cross-connector replay
   contract.
1. No public ack API, public checkpoint mutation API, or durable cursor store.
1. No multi-topic fan-in, gap-free global ordering promise, or exactly-once
   delivery claim.
1. No extraction of schema registry or broader eventing abstractions beyond
   what one working CDC path needs.

## Session Checkpoint (2026-08-02)

- Branch: `chore/adr-support-linux-tox-gates`.
- Completed: ADR-0030 and SF-0013 accepted; public docs baseline completed;
  critical contract tests completed; tox/security/evidence gates completed;
  Salesforce eventing spike planning added to this plan.
- Next session: carry the accepted ADR constraints into implementation and
  contract validation for the first eventing slice.

## Next Steps (Saved 2026-08-03)

1. Implement concrete async gRPC transport wiring for current gRPC contracts.
1. Replace CDC subscriber placeholder with real subscribe flow in
   salesforce/cdc.
1. Add bounded reconnect and replay-resume behavior; keep ack internal.
1. Expand CDC tests for reconnect, replay, ordering guarantees, and failure
   paths.
1. Keep protobuf envelope and Avro payload handling explicit in the CDC
   implementation and tests.
1. Add schema-resolution handling with schema ID support and define cache
   behavior for schema refresh.
1. Add contract coverage for merged events (`record_ids`) and for gap or
   overflow event handling behavior.
1. Document channel naming assumptions and treat channel names as case-
   sensitive in request validation and examples.
1. Keep shadow-store consumer and materialization out of plynth and out of
   the connector.
1. Update docs for runtime-wired status and rerun lint, type, and test gates.

## Archive/Remove Note

This plan is a working artifact. After release closure, archive it under the
change-plan convention or remove it if superseded by final roadmap and ADRs.
