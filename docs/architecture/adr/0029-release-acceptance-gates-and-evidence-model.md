# ADR-0029: Release Acceptance Gates and Evidence Model

## Status

Accepted

## Context

Plynt needs objective release decisions for public-package readiness.

Existing quality checks and architecture decisions are distributed across
multiple documents and workflows. There is no single model that defines which
gates are release-blocking, what evidence is required, and who can accept
exceptions.

This gap increases risk of subjective go/no-go decisions and inconsistent
quality across releases.

## Decision

Plynt will adopt a release acceptance model with explicit gates and evidence:

1. A release is approved only when all blocking gates pass or have a recorded
   exception.
1. Blocking gates include:
   - public API compatibility checks,
   - tox Linux matrix pass for all supported Python versions,
   - supported environment and extras validation,
   - tests and CI stability thresholds,
   - documentation and migration-note readiness,
   - security and dependency policy checks.
1. Each gate must produce evidence artifacts that are linkable from the release
   decision record (for example CI run IDs, tox env-list results, coverage
   reports, compatibility reports, and docs review references).
1. Exceptions require named owner, explicit expiration, risk statement, and
   rollback condition.
1. For public releases, the compatibility gate cannot be waived without an
   explicit owner and expiry documented in the release decision record.
1. Release evidence must be retained for audit and post-release review.
1. Salesforce eventing release slices use the same gate model; eventing-specific
   checks may be added but cannot bypass package-level blocking gates.

## Alternatives Considered

### Option A: Keep informal release sign-off

**Pros:**

- Fastest short-term process.

**Cons:**

- Decision quality depends on individual judgment.
- Weak auditability.

**Why rejected:** Not suitable for public package reliability goals.

### Option B: Block only on CI green status

**Pros:**

- Simple and measurable.

**Cons:**

- Misses compatibility, docs, and exception governance.

**Why rejected:** CI pass alone is necessary but not sufficient.

### Option C: Manual review with no artifact retention

**Pros:**

- Low tooling burden.

**Cons:**

- Poor traceability and weak post-incident analysis.

**Why rejected:** Evidence retention is required for accountable releases.

## Rationale

A concrete gate-and-evidence model improves release consistency and makes
quality decisions repeatable. It allows maintainers to ship confidently while
capturing explicit risk when exceptions are unavoidable.

## Consequences

### Positive

- Objective, auditable go/no-go decisions.
- Better alignment between architecture intent and release execution.
- Faster root-cause analysis when post-release issues occur.

### Negative / Tradeoffs

- More process and artifact management overhead.
- Potentially longer release lead time during initial adoption.

### Risks

- Overly strict gates can delay low-risk fixes.

Mitigations:

1. Classify gates by release type where appropriate.
1. Use time-bound exceptions with explicit owner accountability.

## Related ADRs

- ADR-0001: Architecture Principles
- ADR-0003: Dependency Policy
- ADR-0014: Logging Strategy
- ADR-0022: Upstream Rate Governance
- ADR-0027: Public API Compatibility and Deprecation Policy
- ADR-0028: Supported Environments and Extras Policy
