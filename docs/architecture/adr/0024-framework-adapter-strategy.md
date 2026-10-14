# ADR-0024: Framework Adapter Strategy

## Status

Accepted

## Context

Plynt's product roadmap includes optional integrations for Django, FastAPI,
and Flask. These integrations do not belong in the core packages because
ADR-0001, ADR-0002, and ADR-0003 require the core to remain
framework-agnostic and keep optional dependencies isolated behind extras.

The current roadmap already has separate idea documents for Django, FastAPI,
and Flask, but top-level tracking has still grouped them together. That makes
progress harder to reason about because the three frameworks solve different
problems, have different dependency profiles, and should not advance at the
same pace.

There is also a terminology question: whether these integrations should be
treated as "frameworks" in naming and directory structure, or as
"framework adapters" that translate between plynt's public interfaces and a
host framework's lifecycle, configuration, and dependency model.

Finally, a first implementation target is needed so the repository can move
from idea-stage notes to an executable framework integration plan.

## Decision

Plynt will treat these integrations as **framework adapters** and keep them
under the `plynt.adapters` boundary.

The strategy is:

1. Use the term **framework adapter** consistently in architecture and product
   documentation.
1. Keep framework-facing modules under the `adapters` namespace rather than a
   `frameworks` namespace.
1. Track Django, FastAPI, and Flask as separate roadmap items so each can be
   planned, shipped, or deferred independently.
1. Implement Django first as `plynt[django]`.
1. Treat FastAPI as the next candidate after Django validation.
1. Keep Flask conditional on demonstrated demand because the zero-adapter path
   already works well for its common sync use cases.

## Alternatives Considered

### Option A: Rename the boundary to `frameworks` and describe these modules as frameworks

**Pros:**

- Slightly shorter term in docs.
- Superficially easier for readers who are thinking in product names.

**Cons:**

- Blurs the architectural role of these modules.
- Suggests plynt owns framework runtimes rather than thin integration
  boundaries.
- Conflicts with the existing connector-versus-adapter terminology used across
  the repository.

**Why rejected:** The key decision is about boundary type, not about product
category. "Adapter" is the precise architectural term.

### Option B: Keep the term `adapter` but continue tracking all frameworks as one roadmap item

**Pros:**

- Minimal roadmap editing.
- Leaves sequencing flexible.

**Cons:**

- Hides materially different scope and readiness per framework.
- Makes it harder to mark one framework done without implying progress on all.
- Encourages vague planning instead of ADR-by-ADR delivery.

**Why rejected:** The roadmap should reflect real delivery slices, not a
bucket of unrelated optional integrations.

### Option C: Keep `adapters`, use explicit framework-adapter terminology, and split roadmap tracking per framework

**Pros:**

- Preserves architectural precision.
- Aligns with the layered model and dependency policy.
- Makes delivery and acceptance criteria concrete per framework.
- Supports demand-driven sequencing without coupling all frameworks together.

**Cons:**

- Requires small documentation updates now.
- Adds an explicit prioritization decision.

**Why chosen:** This is the clearest match for plynt's architecture and gives
the most usable roadmap structure.

## Rationale

"Adapter" is the right term because these modules do not define new core
abstractions and do not represent framework-specific business domains. Their
job is to translate plynt's existing public interfaces into framework
conventions such as Django settings and cache aliases, FastAPI lifespan and
dependency injection, or Flask extension wiring.

Keeping the namespace as `adapters` also protects the architecture boundary.
It makes it obvious that these modules depend on the core through public
interfaces only and that no framework-specific assumptions should flow back
into `plynt.base`, `plynt.http`, or `plynt.middleware`.

Django is the best first adapter because its value proposition is concrete and
bounded: configuration bridging and cache integration. That makes it a strong
validation target for optional-framework support without forcing async
lifecycle management or speculative abstraction. FastAPI remains attractive,
but it should follow after one framework adapter has validated the packaging,
namespace, and support model. Flask is intentionally lower priority because
its common usage already works well without additional library code.

## Consequences

### Positive

- Terminology becomes consistent across roadmap, architecture docs, and code.
- Framework work can be planned and shipped one adapter at a time.
- The first implementation target is explicit: `plynt[django]`.
- Future ADRs for FastAPI and Flask can stay focused on framework-specific
  lifecycle and API concerns.

### Negative / Tradeoffs

- Some existing docs need to be updated to use the more explicit term
  "framework adapter".
- Choosing Django first delays FastAPI-specific helper work.

### Risks

- Consumers may assume Django-first means Django-specific patterns are allowed
  into the core.
- The `adapters` namespace could drift into convenience code unrelated to
  boundary translation.

Mitigations:

- Keep adapter implementation behind optional extras only.
- Review adapter imports carefully so framework dependencies do not cross back
  into core packages.
- Require a dedicated ADR for each additional framework adapter before code is
  written.

## Related ADRs

- ADR-0001: Architecture Principles
- ADR-0002: Layered Architecture
- ADR-0003: Dependency Policy
- ADR-0004: Settings and Configuration
- ADR-0010: Caching
