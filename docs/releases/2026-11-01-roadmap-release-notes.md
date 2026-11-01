# Roadmap release preparation — 2026-11-01

## Summary

This candidate makes upstream errors easier to handle and correlate, adds
optional error reporting, and documents application-scoped Salesforce auth.
It includes intentional pre-1.0 error-contract changes. Release-please owns
the eventual version, versioned changelog, tag, and GitHub release.

## What's new

- Catch backend-neutral `TransportTimeoutError` and
  `TransportConnectionError` from built-in HTTP transports.
- Inspect `AuthenticationError.status_code` for failed token responses without
  exposing response bodies in exception messages. Broad `RuntimeError`
  handlers remain compatible.
- Correlate requests through scoped request IDs, outbound headers, logging,
  and Django/ASGI middleware.
- Customize DRF and FastAPI error envelopes while preserving existing defaults.
- Report errors through a vendor-neutral interface or optional `plynt[sentry]`,
  with sanitized context, observed retry attempts, and exception-bound event IDs.
- Use shared Salesforce JWT auth in a tested FastAPI lifespan recipe, with
  documented ownership and cleanup methods.
- Use installed typing metadata and discover framework guides in the adapter
  documentation.

## Migration

Read the [migration guide](../user/migrations/typed-transport-errors.md) before
upgrading. Replace backend-specific network handlers with Plynt types; replace
parsing raw token-failure messages with `AuthenticationError.status_code`.
Do not log the optional sensitive `response_body` or raw exception causes.

`HttpRetryPolicy` recognizes the new timeout/connection types by default.
Protocol-neutral `RetryPolicy` is unchanged; custom classifiers may need updates.
Moved framework guides retain entry points in the user documentation.

## Internal

- Expand deterministic sync/async, adapter, reporting, auth, and installed-wheel
  coverage, including optional Sentry profiles.
- Refresh supported toolchain pins and retain Python 3.12–3.15 checks.

## Evidence reviewed

| Evidence                                                                | Status                                                  |
| ----------------------------------------------------------------------- | ------------------------------------------------------- |
| [Product roadmap](../product/roadmap.md)                                | Shipped scope accepted; other work deferred             |
| [Architecture](../architecture/overview.md), ADR-0035 and ADR-0039–0043 | Architect OK after documentation clarification          |
| [Verification](../reports/2026-11-01-release-verification.md)           | Local matrix/packages pass; tester migration handoff OK |
| [Release gate and explicit reviews](2026-11-01-roadmap-release-gate.md) | Tester, architect, designer, product OK for PR handoff  |
| Remote PR/merge-group checks and secret scanning                        | Not yet run; required before merge                      |

## Limitations and release status

Performance overhead is unmeasured. Local reporting tests do not establish
live Sentry delivery. Live Salesforce CDC/provider validation and other roadmap
work remain deferred; CDC remains **Experimental**, not production accepted.
Dependency audits are scoped and are not an unpublished-source security audit.

This document prepares a PR; it does not claim merge, a tag, publication, or
successful remote checks. The existing protected automation must permit each
subsequent step. No admin override or manual version/tag is authorized.

## Why and version impact

Consumers gain stable failure handling and correlated diagnostics without
mandatory tracker dependencies. The approved error changes are breaking under
the pre-1.0 policy; release-please selects the version from Conventional Commits.

## Artifact register

- Implementation: `7a7b96b33ebccec6ce63b7fca16c156851484843`.
- Main baseline: `ab2d7da473d7ed0a57d625d54bd12e940e1e8dbb`.
- Migration: `docs/user/migrations/typed-transport-errors.md`.
- Verification and sign-off record: linked above.
- Final candidate commit, PR and remote run IDs: registered in the release gate
  and PR handoff once created.
