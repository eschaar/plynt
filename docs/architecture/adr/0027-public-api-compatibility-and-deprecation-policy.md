# ADR-0027: Public API Compatibility and Deprecation Policy

## Status

Accepted

## Context

Plynt is preparing for public package release and needs a clear compatibility
contract for users who depend on stable APIs across upgrades.

Current architecture ADRs define layering, adapters, and boundaries, but there
is no package-level rule for what can change in minor or patch releases, how
deprecations are announced, or how long deprecated surfaces remain available.

Without this policy, teams risk unplanned breakage, inconsistent migration
guidance, and release decisions that are hard to justify.

## Decision

Plynt will adopt a package-level compatibility and deprecation policy:

1. Public API scope includes documented symbols, typed models, adapter
   factories, middleware extension points, and installation extras behavior.
1. Semantic versioning is strict for public surfaces:
   - patch releases fix defects only and do not break documented behavior,
   - minor releases may add capabilities but remain backward compatible,
   - major releases may remove or change public behavior.
1. Any planned removal must follow a two-step deprecation path:
   - first release: mark as deprecated in docs and changelog with replacement,
   - later major release: remove deprecated behavior.
1. Deprecation notice must include target removal version and migration path.
1. Release gates must fail if a known breaking public API change is introduced
   without a major version bump and explicit release note entry.

## Alternatives Considered

### Option A: Best-effort compatibility without explicit policy

**Pros:**

- Minimal process overhead.

**Cons:**

- Inconsistent release decisions.
- Harder upgrade planning for users.

**Why rejected:** Public package consumers need predictable guarantees.

### Option B: Freeze all public APIs indefinitely

**Pros:**

- Maximum short-term stability.

**Cons:**

- Slows architectural evolution.
- Forces permanent support for poor early choices.

**Why rejected:** Plynt needs controlled change, not zero change.

### Option C: Deprecate and remove within the same minor release

**Pros:**

- Faster cleanup.

**Cons:**

- Breaks trust and compatibility expectations.

**Why rejected:** Not acceptable for public package lifecycle.

## Rationale

This policy gives users a stable contract while preserving a path for planned
evolution. It aligns release behavior with semantic versioning and creates a
repeatable process for migration communication and go/no-go review.

## Consequences

### Positive

- Clear compatibility expectations for package consumers.
- Better upgrade planning with explicit deprecation timelines.
- Fewer accidental breaking changes in non-major releases.

### Negative / Tradeoffs

- More release governance work for maintainers.
- Some cleanup work must wait for major-version windows.

### Risks

- Ambiguity around what is considered public may cause disagreement.

Mitigations:

1. Maintain explicit public-surface documentation in package docs.
1. Review potential breaking changes during release acceptance gates.

## Related ADRs

- ADR-0001: Architecture Principles
- ADR-0003: Dependency Policy
- ADR-0009: Service Layer
- ADR-0024: Framework Adapter Strategy
- ADR-0028: Supported Environments and Extras Policy
- ADR-0029: Release Acceptance Gates and Evidence Model
