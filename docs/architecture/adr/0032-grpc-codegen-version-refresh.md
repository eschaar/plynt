# ADR-0032: gRPC Code Generation Version Refresh

**Date:** 2026-10-14
**Status:** Accepted

## Context

ADR-0031 pins the Salesforce Pub/Sub generator to `grpcio-tools==1.83.1`
and aligns consumer runtime minima with generated imports. Version 1.84.0
is now available. The maintainer approved refreshing the generator and
runtime together, separately from the other dependency updates.

Code generation must remain reproducible. Updating only the generator
without reviewing generated runtime checks can break installed consumers.
Updating all runtime minima to their latest releases would also restrict
consumers unnecessarily when the generated code supports older versions.

## Decision

1. Replace ADR-0031's generator pin with `grpcio-tools==1.84.0`.
1. Require `grpcio>=1.84.0,<2` for the refreshed generated gRPC stub.
1. Derive the protobuf minimum from the regenerated code's runtime check.
   Preserve `protobuf>=7.35.1,<8` if that remains the generated requirement.
1. Regenerate both Python files from the unchanged vendored proto. Apply
   only the existing package-relative import normalization.
1. Verify regeneration against committed output and test installed wheels
   at declared CDC runtime minima without code generation tooling.
1. Preserve the `grpc` and `salesforce` extras, Linux Python 3.11-3.14
   support, async-only eventing, and experimental CDC status.

This supersedes only the generator and associated gRPC runtime versions
in ADR-0031. Its installation boundaries and other decisions remain intact.

## Alternatives Considered

### Keep the existing generator

This avoids regeneration but postpones a maintainer-approved tooling refresh.
It remains a valid rollback option if compatibility validation fails.

### Upgrade the generator without runtime alignment

Rejected because generated gRPC imports enforce a runtime minimum.
Consumer metadata must satisfy that requirement.

### Raise every runtime minimum to the latest release

Rejected because installed-version freshness does not establish a need for
higher consumer minima. Test current versions separately from minimum support.

## Rationale

A deliberate exact generator pin preserves reproducibility while reviewed
runtime bounds preserve the existing optional-install contract.
Regeneration, minimum-runtime wheel checks, and the supported Python matrix
provide distinct evidence for this version refresh.

## Consequences

- Consumers using gRPC below 1.84.0 must upgrade for the refreshed stub.
- Generated files change, but the upstream proto and public API do not.
- Future generator refreshes still need deliberate review and verification.
- Provider authentication, opaque replay IDs, and real-org behavior remain
  outside the guarantees established by codegen and local tests.

## Related ADRs

- [ADR-0030](0030-grpc-protocol-boundary.md): protocol and execution boundary.
- [ADR-0031](0031-experimental-release-installation-contract.md):
  installation contract; version choices partially superseded here.
- [SF-0013](../../connectors/salesforce/architecture/adr/sf-0013-salesforce-eventing-architecture.md):
  connector-local eventing semantics.
