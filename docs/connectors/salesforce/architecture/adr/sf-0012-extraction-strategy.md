# SF-0012: Salesforce Integration Extraction Strategy

**Status:** Proposed

## Acceptance Triggers

Keep this ADR in Proposed until all trigger criteria below are true:

1. A target extraction window is scheduled and owned.
1. Contract-freeze scope is complete for the current in-repo Salesforce API.
1. A migration and compatibility policy is approved for downstream consumers.
1. CI and release ownership are defined for the new Salesforce package.
1. A rollback plan exists in case extraction introduces regressions.

**Related ADRs:**

- [SF-0011](sf-0011-ai-connector-boundary.md) — AI Connector Boundary

## Context

Currently, Salesforce integration is embedded in the Plynt core repository.
This couples the core framework to a specific provider, making it harder to
maintain architectural separation of concerns.

### Current State

- `plynt` contains `connectors/salesforce/`
- All consumers depend directly on the monolithic `plynt` package
- Salesforce-specific logic is interleaved with core abstractions

### Desired State

- `plynt` remains a framework-agnostic core library
- Salesforce integration lives in its own repository
- `salesforce-connector` package depends on `plynt`, not the reverse

## Decision

**Extract Salesforce integration to a separate repository while maintaining Plynt as a stable dependency.**

### Dependency Direction

```text
salesforce-connector-package
    ↓ depends on
plynt (core)
```

This keeps the core framework-agnostic and avoids circular dependencies.

## Implementation

### Phase 1: Contract Freeze (in current repository)

1. Confirm the public API surface that external consumers may use:
   - facade entrypoints (e.g., `SalesforceService`)
   - service classes
   - response models and error types
1. Mark the public API in docs
1. Add focused contract tests for that public API
1. Avoid new internal coupling to unrelated modules

**Exit Criteria:**

- API is documented and covered by stable tests
- No unresolved architectural decisions remain

### Phase 2: New Repository Bootstrap

1. Create a new repository for the Salesforce package
1. Copy integration modules, tests, and docs into the new repository
1. Keep package naming and module boundaries explicit and minimal
1. Set CI in the new repository: lint, type checks, tests

**Exit Criteria:**

- New repository builds and tests pass independently
- Dependency direction remains `salesforce-package -> plynt`

### Phase 3: Local Two-Repo Development Workflow

Use a multi-root workspace with both repositories open.

**Recommended local workflow:**

```bash
# In salesforce-connector workspace
source .venv/bin/activate
pip install -e ../plynt           # local editable Plynt
pytest -q                          # test against local changes
```

**Note:** Use editable install only for local development. In CI and releases,
pin Plynt to a fixed version or tag.

**Exit Criteria:**

- Developer workflow is stable and documented
- Both repositories can evolve together safely

### Phase 4: Consumer Cutover

1. Replace in-repo Salesforce imports with the new package
1. Keep compatibility shims only if needed and time-box them
1. Publish migration notes with import examples and version guidance

**Exit Criteria:**

- Consumers import Salesforce integration from the new repository
- Backward-compatibility policy is documented

### Phase 5: Cleanup in Plynt

1. Remove old Salesforce integration modules from Plynt
1. Remove obsolete tests and docs from Plynt
1. Keep a short pointer in docs to the external package location

**Exit Criteria:**

- Plynt no longer contains Salesforce integration implementation code
- Remaining docs clearly direct users to the external package

## Branch and Release Guidance

**Preferred order when both repos need changes:**

1. Plynt change first
1. Salesforce package update second
1. Plynt release/tag
1. Salesforce dependency bump

Avoid long-lived branches that span both repos without integration checks.

## Testing Guidance During Migration

- Keep current fast mocked tests as baseline
- Add a small VCR.py-backed smoke layer in the Salesforce package
- Keep optional live backend tests separate and opt-in

## Risks and Mitigations

| Risk                                   | Mitigation                                                |
| -------------------------------------- | --------------------------------------------------------- |
| Hidden coupling to Plynt internals     | Enforce public API usage only and contract tests          |
| Dependency drift between repos         | CI matrix with fixed and latest compatible Plynt versions |
| Extraction causes user-facing breakage | Clear migration docs and compatibility window             |

## Consequences

**Positive:**

- Plynt remains truly framework-agnostic
- Salesforce integration can evolve at its own pace
- Core abstractions are protected from provider-specific coupling
- Clear separation of concerns

**Negative:**

- Requires multi-repo coordination during development
- Temporary dual-maintenance window during phases 2–4
- More complex dependency management for consumers

## Alternatives Considered

1. **Keep Salesforce in Plynt forever**
   - Rejected: violates core framework-agnostic principle
1. **Make Salesforce optional via extras**
   - Rejected: coupling still exists; doesn't solve architectural problem
1. **Immediate extraction without phases**
   - Rejected: too risky; phased approach reduces breakage

## Next Steps

1. Keep this ADR Proposed until all acceptance triggers are met
1. Proceed with Phase 1: contract freeze and documentation
1. Record phase completion milestones in follow-up PRs
