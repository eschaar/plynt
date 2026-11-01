# ADR-0044: Tested gRPC Toolchain Upgrade Policy

**Date:** 2026-11-01
**Status:** Accepted

## Context

ADR-0031 established reproducible generation and optional runtime installation.
ADR-0032 approved a coordinated refresh to gRPC 1.84.0, recording exact versions
as a decision for that refresh. Those historical selections must not become
permanent constraints that require a new ADR for every routine version update.

The maintainer explicitly approved both this policy clarification and a full
gRPC 1.85.0 generator/runtime refresh. This ADR authorizes that implementation;
it does not assert that regeneration, compatibility tests, or release gates
have already passed. At acceptance, the manifest and generated stub still use
1.84.0.

## Decision

### Durable policy and bounded authorization

1. Exact toolchain pins belong in version-controlled dependency manifests;
   generated artifacts record the generator and enforced runtime requirements.
   ADRs govern compatibility and upgrade gates, not a forever exact version.
1. Approve `grpcio-tools==1.85.0` as the next development generator and a
   coordinated gRPC runtime refresh. Derive the consumer minimum from its
   regenerated stub; use `grpcio>=1.85.0,<2` if the stub requires 1.85.0.
   Derive the protobuf minimum independently from regenerated message checks.
1. Routine subsequent patch/minor upgrades within the existing gRPC 1.x and
   protobuf 7.x boundaries may reference this ADR without a new version-only
   ADR. Each update requires deliberate maintainer review and all gates below.
   Automated proposals are not approval to merge or release.
1. Keep finite runtime upper bounds: `grpcio<2` and `protobuf<8`. Do not use
   unbounded dependencies or equate the newest runtime with the required floor.
   A higher floor needs generated-code or documented compatibility/security
   evidence and explicit review of its consumer impact.
1. Major tool/runtime upgrades, changes to these upper bounds, incompatible
   generated behavior, public contracts, supported environments, dependency
   placement, or execution boundaries require separate architecture review
   and an accepted decision before implementation, with migration planning.

This supersedes only ADR-0032's fixed version selections and clarifies the
placement and update lifecycle of the pins established in ADR-0031. Their
reproducibility, installation, and validation requirements remain binding.
Historical decisions remain intact; this ADR governs subsequent refreshes.

### Required gates for every refresh

1. Record the selected exact development generator pin and its resolved
   toolchain, including protobuf, in review evidence. Regeneration must use
   that documented environment, not whatever generator is locally installed.
1. Regenerate both Python artifacts from the unchanged vendored proto using
   the existing generation target. Allow only the existing package-relative
   import normalization; do not hand-edit or disable generated runtime checks.
   A proto/source update is a separate reviewed change with provenance.
1. Inspect both generated runtime checks and align manifest minima with their
   requirements and any reviewed compatibility/security floors. Preserve an
   existing protobuf minimum when regeneration and testing justify it; do not
   assume it remains valid or raise it merely to match the generator version.
1. Run `make salesforce-cdc-proto-verify` with the selected pinned toolchain.
   Temporary regeneration must match both committed artifacts exactly. Review
   generated diffs for changes beyond version markers; unexplained behavior
   changes block the routine-upgrade path.
1. Build the wheel from the source distribution. Test clean core and documented
   extra profiles without development/codegen tooling, including generic gRPC
   and CDC via `plynt[grpc,salesforce]`. Check installed CDC at exact declared
   runtime minima separately from current versions within the allowed bounds,
   on the oldest and newest supported Linux Python versions.
1. Run the complete test profile across the current supported Linux Python
   3.12-3.15 matrix, including local gRPC and CDC tests. Retain the existing
   100% statement-coverage gate in its configured scope and quality/security
   checks; generated output verification is separate from measured coverage.
1. Keep manifests, generation/provenance documentation, minimum-runtime
   installation checks, and consumer migration/release notes consistent.
   Record tested versions, commands, results, and the implementation revision
   as evidence under ADR-0029. Prior-version results cannot validate a refresh.
1. If a gate fails or compatibility is unclear, stop the refresh and escalate.
   Keep or restore the previous coherent generator/artifact/runtime set;
   never retain a partial generator-only or metadata-only upgrade.

### Unchanged architectural boundaries

gRPC and protobuf remain optional in `plynt[grpc]`; Salesforce dependencies
remain in `plynt[salesforce]`. Codegen tooling is development-only and is not
required to import or consume installed wheels. Core-only imports must remain
usable without these extras.

ADR-0030's generic protocol boundary and the async-only phase-1 execution model
remain unchanged. No transport contract, CDC/replay semantics, new dependency,
or installation extra is introduced here. The refresh does not expand the
support matrix or establish provider authentication, real-org replay fidelity,
long-running reliability, production readiness, or release authorization.

## Alternatives Considered

- **New ADR per exact version:** preserves approval history but couples durable
  architecture to routine maintenance. Retain version history in reviewed
  manifests, artifacts, commits, and verification evidence instead.
- **Floating generator or runtime ranges without upper bounds:** rejected
  because output becomes non-reproducible and compatibility scope uncontrolled.
- **Generator-only refresh or latest-only testing:** rejected because consumers
  can fail generated import checks at otherwise declared supported minima.

## Consequences

Routine maintenance no longer requires rewriting accepted historical decisions.
The engineer must deliver a coherent, reproducible, tested upgrade and document
any raised consumer floor. The named 1.85.0 refresh remains pending engineering
and verification; architectural acceptance is not test evidence.

## Related ADRs

- [ADR-0003](0003-dependency-policy.md): minimal core and optional dependencies.
- [ADR-0028](0028-supported-environments-and-extras-policy.md): environment policy.
- [ADR-0029](0029-release-acceptance-gates-and-evidence-model.md): evidence gates.
- [ADR-0030](0030-grpc-protocol-boundary.md): unchanged protocol boundary.
- [ADR-0031](0031-experimental-release-installation-contract.md): installation
  and reproducibility contract.
- [ADR-0032](0032-grpc-codegen-version-refresh.md): historical 1.84.0 refresh.
- [ADR-0033](0033-python-315-support-and-local-pyenv.md) and
  [ADR-0034](0034-django-6-support.md): current Python support matrix.
