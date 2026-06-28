# SF-0012: Salesforce Integration Extraction Strategy

**Status:** Proposed

**Related ADRs:**

- [SF-0011](sf-0011-ai-connector-boundary.md) — AI Connector Boundary

## Context

Currently, Salesforce integration is embedded in the Plynth core repository.
This couples the core framework to a specific provider, making it harder to
maintain architectural separation of concerns.

### Current State

- `plynth` contains `connectors/salesforce/`
- All consumers depend directly on the monolithic `plynth` package
- Salesforce-specific logic is interleaved with core abstractions

### Desired State

- `plynth` remains a framework-agnostic core library
- Salesforce integration lives in its own repository
- `salesforce-connector` package depends on `plynth`, not the reverse

## Decision

**Extract Salesforce integration to a separate repository while maintaining Plynth as a stable dependency.**

### Dependency Direction

```text
salesforce-connector-package
    ↓ depends on
plynth (core)
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
- Dependency direction remains `salesforce-package -> plynth`

### Phase 3: Local Two-Repo Development Workflow

Use a multi-root workspace with both repositories open.

**Recommended local workflow:**

```bash
# In salesforce-connector workspace
source .venv/bin/activate
pip install -e ../plynth           # local editable Plynth
pytest -q                          # test against local changes
```

**Note:** Use editable install only for local development. In CI and releases,
pin Plynth to a fixed version or tag.

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

### Phase 5: Cleanup in Plynth

1. Remove old Salesforce integration modules from Plynth
1. Remove obsolete tests and docs from Plynth
1. Keep a short pointer in docs to the external package location

**Exit Criteria:**

- Plynth no longer contains Salesforce integration implementation code
- Remaining docs clearly direct users to the external package

## Branch and Release Guidance

**Preferred order when both repos need changes:**

1. Plynth change first
1. Salesforce package update second
1. Plynth release/tag
1. Salesforce dependency bump

Avoid long-lived branches that span both repos without integration checks.

## Testing Guidance During Migration

- Keep current fast mocked tests as baseline
- Add a small VCR.py-backed smoke layer in the Salesforce package
- Keep optional live backend tests separate and opt-in

## Risks and Mitigations

| Risk                                   | Mitigation                                                 |
| -------------------------------------- | ---------------------------------------------------------- |
| Hidden coupling to Plynth internals    | Enforce public API usage only and contract tests           |
| Dependency drift between repos         | CI matrix with fixed and latest compatible Plynth versions |
| Extraction causes user-facing breakage | Clear migration docs and compatibility window              |

## Consequences

**Positive:**

- Plynth remains truly framework-agnostic
- Salesforce integration can evolve at its own pace
- Core abstractions are protected from provider-specific coupling
- Clear separation of concerns

**Negative:**

- Requires multi-repo coordination during development
- Temporary dual-maintenance window during phases 2–4
- More complex dependency management for consumers

## Alternatives Considered

1. **Keep Salesforce in Plynth forever**
   - Rejected: violates core framework-agnostic principle
1. **Make Salesforce optional via extras**
   - Rejected: coupling still exists; doesn't solve architectural problem
1. **Immediate extraction without phases**
   - Rejected: too risky; phased approach reduces breakage

## Next Steps

1. Confirm this ADR
1. Proceed with Phase 1: contract freeze and documentation
1. Record phase completion milestones in follow-up PRs
