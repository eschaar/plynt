# ADR-0028: Supported Environments and Extras Policy

## Status

Accepted

## Context

Plynth uses a modular package model with optional extras and framework
adapters. Public release readiness requires explicit support boundaries for
Python versions, runtime environments, and optional install combinations.

Without a formal policy, consumers cannot reliably know which environments are
supported, and maintainers cannot apply consistent CI scope or triage rules.

## Decision

Plynth will publish and enforce a supported-environments and extras policy:

1. The supported operating system family is Linux only.
1. The baseline support matrix is concrete: Python 3.11, 3.12, 3.13, and 3.14
   on Linux.
1. tox multi-version validation is capped at five Python versions maximum.
1. A fifth version may be added as the newest stable Python release while
   keeping Linux as the only supported OS family.
1. Supported environments are defined by tested combinations of:
   - Python runtime version from the supported Linux matrix,
   - selected optional extras.
1. Core package installation must remain framework-agnostic and usable without
   optional adapter extras.
1. Each optional extra must declare:
   - ownership,
   - minimum support assumptions,
   - compatibility test scope in CI.
1. New extras or support-matrix changes require ADR review when they alter
   dependency strategy, packaging boundaries, or release gate scope.
1. Unsupported environment combinations are allowed but marked as out of
   contract and not release-blocking.

Salesforce eventing work must conform to the same optional-extra contract and
cannot redefine core support boundaries.

## Alternatives Considered

### Option A: Support all environments that "probably work"

**Pros:**

- Low upfront governance.

**Cons:**

- Unclear support contract.
- Higher support burden and incident risk.

**Why rejected:** Public packages need explicit support boundaries.

### Option B: Support only one runtime and one install profile

**Pros:**

- Simple test matrix.

**Cons:**

- Limits adoption and adapter use cases.

**Why rejected:** Too restrictive for plynth's adapter strategy.

### Option C: Make all extras fully tier-1 from day one

**Pros:**

- Uniform support story.

**Cons:**

- Unsustainable test and maintenance cost at current maturity.

**Why rejected:** Must stage support based on validated evidence.

## Rationale

Explicit environment and extras boundaries are required to keep plynth stable
while preserving modular adoption. The policy aligns user expectations,
dependency control, and CI investment with package maturity.

## Consequences

### Positive

- Clear support contract for package consumers.
- Better prioritization for CI and compatibility testing.
- Controlled growth of optional extras.

### Negative / Tradeoffs

- Some user scenarios remain intentionally out of support scope.
- Additional documentation and matrix maintenance work.

### Risks

- Support matrix drift if docs, CI, and release gates diverge.

Mitigations:

1. Treat support matrix updates as release-governed changes.
1. Require evidence updates when changing supported combinations.

## Related ADRs

- ADR-0001: Architecture Principles
- ADR-0002: Layered Architecture
- ADR-0003: Dependency Policy
- ADR-0024: Framework Adapter Strategy
- ADR-0027: Public API Compatibility and Deprecation Policy
- ADR-0029: Release Acceptance Gates and Evidence Model
