# Salesforce Extraction Plan (Preparation Only)

This document describes a migration plan to move the Salesforce integration
to its own repository while keeping Plynth as the base dependency.

Status: planning only. Nothing in this plan has been executed yet.

## Goal

- Keep Plynth as the stable core library.
- Make the Salesforce integration an external consumer package.
- Preserve compatibility during migration.

## Target Dependency Direction

- `salesforce-package` depends on `plynth`.
- `plynth` does not depend on `salesforce-package`.

This keeps the core framework-agnostic and avoids circular dependencies.

## Migration Strategy

Use a phased migration with a temporary dual-maintenance window.

### Phase 1: Contract Freeze (in current repository)

1. Confirm the public API surface that external consumers may use.
1. Mark the public API in docs:
   - facade entrypoints
   - service classes
   - response models and error types
1. Add focused contract tests for that public API.
1. Avoid new internal coupling to unrelated modules.

Exit criteria:

- API is documented and covered by stable tests.
- No unresolved architectural decisions remain.

### Phase 2: New Repository Bootstrap (no runtime switch yet)

1. Create a new repository for the Salesforce package.
1. Copy integration modules, tests, and docs into the new repository.
1. Keep package naming and module boundaries explicit and minimal.
1. Set CI in the new repository:
   - lint
   - type checks
   - tests

Exit criteria:

- New repository builds and tests pass on its own.
- Dependency direction remains `salesforce-package -> plynth`.

### Phase 3: Local Two-Repo Development Workflow

Use a multi-root workspace with both repositories open.

Recommended local workflow:

1. Activate the Salesforce package virtual environment.
1. Install local Plynth in editable mode.
1. Run Salesforce package tests against local Plynth changes.

Example command sequence:

```bash
source .venv/bin/activate
pip install -e ../plynth
pytest -q
```

Notes:

- Use editable install only for local development.
- In CI and releases, pin Plynth to a fixed version or tag.

Exit criteria:

- Developer workflow is stable and documented.
- Both repositories can evolve together safely.

### Phase 4: Consumer Cutover

1. Replace in-repo Salesforce imports in consumers with the new package.
1. Keep compatibility shims only if needed and time-box them.
1. Publish migration notes with import examples and version guidance.

Exit criteria:

- Consumers import Salesforce integration from the new repository.
- Backward-compatibility policy is documented.

### Phase 5: Cleanup in Plynth

1. Remove old Salesforce integration modules from Plynth.
1. Remove obsolete tests and docs from Plynth.
1. Keep a short pointer in docs to the external package location.

Exit criteria:

- Plynth no longer contains Salesforce integration implementation code.
- Remaining docs clearly direct users to the external package.

## Branch and Release Guidance

- Prefer this order when both repos need changes:
  1. Plynth change first
  1. Salesforce package update second
  1. Plynth release/tag
  1. Salesforce dependency bump
- Avoid long-lived branches that span both repos without integration checks.

## Testing Guidance During Migration

- Keep current fast mocked tests as baseline.
- Add a small VCR-backed smoke layer in the Salesforce package.
- Keep optional live backend tests separate and opt-in.

## Risks and Mitigations

- Risk: hidden coupling to Plynth internals.
  - Mitigation: enforce public API usage only and contract tests.
- Risk: dependency drift between repos.
  - Mitigation: CI matrix with fixed and latest compatible Plynth versions.
- Risk: extraction causes user-facing breakage.
  - Mitigation: clear migration docs and compatibility window.

## Decision Log Reminder

If migration requires changes to:

- dependency policy,
- core abstractions,
- installation model, or
- public API guarantees,

stop and record an ADR decision before implementation.
