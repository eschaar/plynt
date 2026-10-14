# ADR-0035: Pre-1.0 Versioning Policy

**Date:** 2026-10-14
**Status:** Accepted

## Context

ADR-0027 requires major releases for incompatible public changes.
The repository is still in private 0.x development, and the maintainer
explicitly approved minor releases for breaking changes before 1.0.
The Python minimum and Django upgrade already carry breaking markers.

Without an explicit release-please option, these markers select 1.0.0.
Removing the markers would hide real incompatibilities from release notes.

## Decision

1. Enable `bump-minor-pre-major` for the root release-please package.
1. While the current version is below 1.0.0, breaking changes produce a
   minor release. Features remain minor and ordinary fixes remain patch.
1. From 1.0.0 onward, breaking changes produce a major release.
   The option does not suppress major bumps after that boundary.
1. Preserve `!`, `BREAKING CHANGE` notes, and migration documentation.
   Versioning flexibility does not imply backward compatibility.
1. During 0.x development, explicitly approved removals may ship in a
   breaking minor release without a prior deprecation release.
   This covers the approved Python 3.11 and Django 5.2 removal.
1. CI/CD and release-please remain responsible for version numbers,
   release PRs, changelogs, and tags. Do not hardcode the next release.

This is a pre-1.0 exception to ADR-0027's major-release and two-step
deprecation requirements. Its other requirements remain in force.
The exception depends on the version boundary, not repository visibility.
Publishing the repository does not automatically change this setting.

## Alternatives Considered

### Release 1.0.0 immediately

Rejected because the maintainer has not approved a stable 1.0 milestone.

### Remove breaking markers

Rejected because the Python and Django installation changes remain
incompatible regardless of the selected version increment.

### Override one release version

Rejected because a one-off version override would not establish a repeatable
0.x policy and would interfere with automation-owned version selection.

## Rationale

The native release-please option preserves accurate change classification
while distinguishing initial development from the stable compatibility
contract. It automatically returns to major bumps at the 1.0 boundary.

## Consequences

- A breaking change from 0.9.5 selects 0.10.0, not 1.0.0.
- A breaking change from 1.0.0 selects 2.0.0.
- Consumers must read migration notes before upgrading between 0.x minors.
- Stable releases still require ADR-0027's deprecation and major policy.
- Local version-selection tests do not publish or approve a release.

## Related ADRs

- [ADR-0027](0027-public-api-compatibility-and-deprecation-policy.md):
  compatibility policy with this pre-1.0 exception.
- [ADR-0029](0029-release-acceptance-gates-and-evidence-model.md):
  release acceptance remains required.
- [ADR-0034](0034-django-6-support.md): approved incompatible upgrade.
