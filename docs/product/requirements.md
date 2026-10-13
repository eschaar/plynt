# Plynth Product Requirements

This document defines the current product requirements for plynth.
It complements the roadmap and should stay aligned with ADR decisions.

______________________________________________________________________

## Functional Requirements

### Core Platform

1. Provide protocol-agnostic transport abstractions for sync and async use.
1. Provide explicit Request and Response models with typed behavior.
1. Provide composable middleware for cross-cutting concerns.
1. Provide typed settings with environment-driven configuration.
1. Provide typed retry and typed error mapping behavior.

### HTTP Foundation

1. Provide production-ready sync and async HTTP transports.
1. Provide typed auth configuration and auth middleware wiring.
1. Provide API client and service base classes for reusable integrations.

### Connector Validation

1. Keep Salesforce connector inside the repository until extraction criteria are
   met.
1. Maintain sync and async parity for implemented Salesforce REST capabilities.
1. Keep connector logic generic and policy-neutral.

### Experimental Eventing

1. Keep generic gRPC protocol concerns under the optional `grpc` extra.
1. Keep Salesforce CDC flow control, replay, checkpoints, and Avro semantics
   inside the Salesforce connector.
1. Preserve the async-only phase-1 boundary in ADR-0030 and SF-0013.
1. Install CDC through `plynth[grpc,salesforce]`, including real Avro decoding.
1. Keep CDC experimental until real-org authentication, schemas, replay
   fidelity, and long-running operation have acceptance evidence.

______________________________________________________________________

## Non-Functional Requirements

1. Keep core framework-agnostic.
1. Keep core dependency surface minimal.
1. Keep architecture decisions ADR-driven.
1. Keep deterministic tests and reproducible quality checks.
1. Keep documentation aligned with shipped behavior.

______________________________________________________________________

## Release Requirements

1. Versioning is driven by release-please and Git tags.
1. Tag format is `X.Y.Z`; GitHub release title format is `vX.Y.Z`.
1. No manual tagging for normal release flow.
1. Publish workflow must use OIDC (no static PyPI token in workflow).
1. PyPI publish remains explicitly controlled by CI guard flag.
1. Require the complete test profile on supported Linux Python 3.11-3.15
   and isolated installed-wheel checks under ADR-0031.
1. Include Python 3.15 and local pyenv bootstrap under ADR-0033; CI continues
   to provision interpreters through setup-python.
1. Enforce 100% statement coverage within the configured source scope;
   do not equate coverage with branch coverage or external-provider validation.
1. Verify pinned CDC code generation and declared runtime minima.
1. Keep local results, revision-specific CI evidence, and external-provider
   acceptance checks distinct.
1. Configure any prerelease versions or tags through CI/CD and release-please;
   do not create experimental RC versions or tags manually.

______________________________________________________________________

## Governance Requirements

1. Do not commit directly to `main` or `master` unless explicitly agreed.
1. Start functional work on a dedicated branch.
1. Check whether a branch already exists remotely and whether it is already
   merged.
1. If a branch is already merged remotely, create a new branch for new work.

______________________________________________________________________

## Traceability

- Vision: [vision.md](vision.md)
- Roadmap: [roadmap.md](roadmap.md)
- Architecture decisions: [../architecture/adr](../architecture/adr)
- Current hardening evidence:
  [October experimental candidate](../releases/2026-10-13-experimental-rc-hardening-evidence.md)
