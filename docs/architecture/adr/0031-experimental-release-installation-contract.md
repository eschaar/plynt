# ADR-0031: Experimental Release Installation Contract

**Date:** 2026-10-13
**Status:** Accepted

## Context

The first experimental release candidate must work outside an editable
development environment. The current Salesforce CDC decoder requires
`fastavro`, but no extra installs it. Vendored Pub/Sub messages also require
newer gRPC and protobuf runtimes than the package metadata declares.

Existing test profiles omit gRPC and FastAPI, while generator versions are
unbounded. Passing tests in a populated development environment therefore
does not establish that documented installations or code generation work.
The maintainer delegated the installation decision for this hardening slice.

The hardening audit also found advisories in the installed PyJWT runtime
and the transitive development packages urllib3 and virtualenv. Security
floors must exclude those versions without adding core runtime dependencies.

## Decision

1. Add `fastavro>=1.13.1,<2` to the existing `salesforce` extra. Do not add
   an eventing extra or dependencies to the core. The CDC installation
   remains `plynt[grpc,salesforce]`, as defined in SF-0013.
1. Align the `grpc` extra with the committed generated code:
   `grpcio>=1.83.1,<2` and `protobuf>=7.35.1,<8`.
1. Pin the development generator to `grpcio-tools==1.83.1`. Code generation
   remains deliberate, local, and reviewed. CI regenerates only into a
   temporary directory to compare against committed files.
1. Require `PyJWT>=2.15.0,<3` in the Salesforce extra. Add development-only
   floors `urllib3>=2.8.0,<3` and `virtualenv>=21.7.13,<22` to prevent
   retaining vulnerable transitive tooling versions during bootstrap.
   Bootstrap local and CI package managers with `pip>=26.2,<27`, including
   fresh wheel environments. Do not add these tooling packages to the core.
1. Install every implemented runtime extra in the full test profile,
   including FastAPI, gRPC, and Salesforce's real Avro decoder. Keep
   isolated core and extra installation smoke tests separate from that profile.
1. Preserve HTTP package exports in core-only installations. Report a missing
   `httpx2` dependency when constructing its concrete transport, not when
   importing clients or errors for a caller-supplied transport. Do not add
   lazy module export hooks or change public symbol names.
1. Build a wheel from the source distribution and smoke-test clean
   installations for core, HTTP, gRPC, Salesforce CDC, Django, DRF, and
   FastAPI without bundled setuptools or codegen tooling. Remove Python
   3.11's seeded setuptools from these environments; it is not needed to
   consume a wheel. Verify declared minimum CDC runtime versions separately.
1. Keep the Linux Python 3.11-3.14 support matrix unchanged. Run the complete
   test profile on all four versions and isolated wheel profiles on the
   oldest and newest supported versions.
1. Treat CDC as experimental until real Salesforce validation establishes
   auth, schemas, replay cursor fidelity, and long-running behavior.
   Do not enable PyPI publishing or create a release tag during hardening.

## Alternatives Considered

### Separate CDC extra

This would avoid installing Avro for REST-only Salesforce consumers.
Rejected for this release because it changes SF-0013's documented composition
and adds another installation boundary for one small connector dependency.
Revisit only with concrete install-size or compatibility evidence.

### Avro in the generic gRPC extra

Rejected because Avro is a Salesforce payload concern, not a gRPC protocol
requirement. Non-Salesforce gRPC users should not install an unused decoder.

### Caller-managed Avro and permissive runtime minima

Rejected because the built-in decoder and vendored stub would remain unusable
under otherwise documented installations. Informational errors cannot replace
an accurate dependency contract.

## Rationale

The selected approach repairs the existing installation promise without new
core abstractions or runtime execution models. Exact development codegen and
compatible runtime ranges serve different needs: reproducible committed output
versus consumer dependency resolution.

Testing installed distributions complements, rather than replaces, unit,
HTTP-level, and real local gRPC tests. No smoke test calls a remote provider.

## Consequences

### Positive

- The documented CDC installation includes its built-in decoder.
- Runtime metadata agrees with generated imports.
- Missing optional dependencies cannot silently remove FastAPI from full CI.
- Distribution tests detect missing files and editable-install assumptions.

### Tradeoffs

- REST-only Salesforce consumers also install the Avro runtime.
- Existing environments with older gRPC or protobuf must upgrade to use this
  version. This requires explicit release notes.
- The experimental RC is not a production-readiness claim for external APIs.

## Related ADRs

- [ADR-0003](0003-dependency-policy.md): dependency policy.
- [ADR-0028](0028-supported-environments-and-extras-policy.md): support matrix.
- [ADR-0029](0029-release-acceptance-gates-and-evidence-model.md): release gates.
- [ADR-0030](0030-grpc-protocol-boundary.md): generic gRPC boundary.
- [SF-0013](../../connectors/salesforce/architecture/adr/sf-0013-salesforce-eventing-architecture.md):
  connector-scoped CDC and its canonical installation.
