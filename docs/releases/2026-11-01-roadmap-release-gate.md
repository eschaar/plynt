# Roadmap Release Gate

Date: 2026-11-01
Branch: `feature/roadmap-development`
Reviewed implementation: `7a7b96b33ebccec6ce63b7fca16c156851484843`
Actual main baseline: `ab2d7da473d7ed0a57d625d54bd12e940e1e8dbb`
Decision: **PR handoff complete. Documentation/reviews and SSH push passed;
merge and publication await current remote gates.**

## Scope

The complete branch comparison contains 108 changed files, not just the
latest lifespan recipe and roadmap updates. It includes:

- Typed transport and authentication errors, including intentional breaks
  governed by ADR-0039 and the pre-1.0 policy in ADR-0035.
- Request-ID context, outbound propagation, logging, and Django/ASGI
  middleware; configurable DRF and FastAPI error envelopes.
- Vendor-neutral error reporting, observed retry context, exception-bound
  event IDs, and an optional Sentry integration under ADR-0041 through
  ADR-0043.
- OAuth2 cleanup methods, shared Salesforce JWT authentication, the tested
  FastAPI lifespan recipe, installed typing metadata, and reorganized guides.

Unrelated local shell changes are not repository release scope.
Other roadmap work and live Salesforce CDC validation remain deferred.
CDC retains its **Experimental** status; local tests are not provider
acceptance or a claim of production readiness.

## Current Evidence

The [tester report](../reports/2026-11-01-release-verification.md) records
commands, results, exact revisions, limitations, and its explicit verdict.

| Gate                                                  | Result                                                                |
| ----------------------------------------------------- | --------------------------------------------------------------------- |
| `make check`                                          | Pass; 2,553 tests, 3 external deselections, 100% statements           |
| Wheel-installed tox, Python 3.12-3.15                 | Pass on all four versions                                             |
| Nine wheel profiles, Python 3.12 and 3.15             | Pass, including Sentry and CDC minima                                 |
| Proto drift and distribution metadata                 | Pass locally                                                          |
| Dependency consistency and known-vulnerability audits | Pass within recorded audit scope                                      |
| Public API comparison                                 | Approved breaks identified; migration reviewed by tester and designer |
| Migration notes and final changelog                   | Migration reviewed; unversioned release packaging prepared            |
| Current PR/merge-group CI and secret scan             | PR #79 opened; current remote checks pending                          |

Performance overhead has not been benchmarked. Observability behavior was
tested locally, including sanitization and in-memory Sentry delivery; no
live tracker was contacted. Audits do not cover unpublished Plynt source.

## Sign-Off Record

| Perspective | Verdict                                      | Scope, freshness, and next action                                                                                |
| ----------- | -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Tester      | PR handoff OK; merge/publication pending     | Revision-matched local evidence reused; migration reviewed; current remote CI required later                     |
| Architect   | PR handoff OK after documentation correction | Complete branch plus migration and ADR/overview clarification reviewed; HTTP-specific retry boundary preserved   |
| Designer    | PR handoff OK                                | Complete branch and current migration reviewed; contracts/defaults/lifecycle consistent; 263 scoped links passed |
| Product     | Business scope and PR handoff OK             | Final review accepts scope, deferrals and reconciled records; docs must be committed with candidate              |
| Release     | PR handoff OK; remote checks pending         | SSH read verified on resumption; unchanged implementation; no merge/publication approval claimed                 |

All reviews cover implementation and base above plus the current documentation
candidate. No source or package metadata changed after local verification.
No time-bound gate exception exists. User authorization does not replace reviews.

### Review rationale and residual risk

- Tester: migration accurately covers typed exceptions, sensitive token bodies,
  and the HTTP/neutral retry distinction. Local evidence remains fresh for the
  unchanged implementation. Release owns obtaining current remote CI.
- Architect: initial NOK identified ambiguous retry wording in ADR-0039 and a
  missing system-style declaration. The owning architect clarified recognition
  as `HttpRetryPolicy` only, kept neutral `RetryPolicy` unchanged, declared the
  library backend-only, and returned explicit OK. No behavior or decision changed.
- Designer: errors, request-ID propagation, envelope defaults, event-ID binding,
  observed retries, shared-auth cleanup, typing, and guide relocation match the
  accepted contracts. No design blocker; applications own telemetry configuration.
- Product: shipped scope and intentional pre-1.0 breaks accepted. Initial
  handoff NOK required reconciling stale gate statements. After reconciliation
  product returned explicit handoff OK for unchanged implementation plus docs.
- Shared residual risk: intentional consumer compatibility breaks require the
  migration guide; performance is unmeasured, provider validation deferred,
  CDC Experimental. These are disclosed limitations, not passed checks.

## Blockers and Owners

1. **Release:** authentication and PR handoff are resolved;
   obtain current Check, Verify, Distribution (including Sentry), Commit, and
   Security evidence before merge. No gate bypass or workflow removal.

User explicitly routed documentation completion, owner reviews, surgical fixes,
and the protected release flow. No new routing request is needed for these steps.

## Automation and Protection

GitHub's active `main` ruleset requires a PR, resolved review threads,
strict current status checks, and prohibits branch deletion and non-fast-forward
updates. It has no bypass actors. Required checks include all four Python
tests, dependency/secret scanning, commit validation, formatting/type checks,
proto drift, sdist-to-wheel build, and the existing isolated wheel profiles.
The Sentry profile also runs in Distribution and must be checked, even though
it is not yet listed as a required ruleset context.

`release.yml` uses release-please on `main` to maintain the release PR and
create its version, changelog, tag, and GitHub release after merge.
`publish.yml` currently enables PyPI publication for qualifying releases,
subject to the existing `pypi` environment and trusted-publisher controls.
The older hardening record's disabled-publication state is historical,
not current configuration.

The manifest remains `0.11.1`. No next version is selected. Existing changelog
entries are unchanged; any eventual unversioned preparation must preserve
release-please ownership of versioned entries. Do not manually create tags,
versions, releases, or bypass protections.

## Artifact Register

- Verification: `docs/reports/2026-11-01-release-verification.md`.
- Release gate and sign-off record: this document.
- Migration: `docs/user/migrations/typed-transport-errors.md`, reviewed with links
  in user README, reference README, and error-handling guide; inclusion required.
- Architecture clarification: ADR-0039 and architecture overview, owner-reviewed.
- Release notes: `docs/releases/2026-11-01-roadmap-release-notes.md`.
- Changelog: unversioned preparation in `CHANGELOG.md`; versioned entries intact.
- Documentation candidate commit: `3d87a933daa9166301977082c5b9c032d1516256`.
- Packaging validation: Markdown lint, whitespace checks and all applicable
  pre-commit hooks passed after formatter normalization; no source change.
- Authentication: earlier SSH/HTTPS push attempts failed. On resumption,
  batch-mode SSH `git ls-remote origin HEAD` succeeded against the single
  configured SSH push destination; main still matches the baseline above.
- Freshness: changes since the verified implementation are reviewed
  documentation and release records only; no source or package metadata drift.
- SSH push succeeded for candidate `ade65c6a410425825b89478d9bf5f4b612c34c2b`.
- Remote branch: `feature/roadmap-development`.
- PR: [#79](https://github.com/eschaar/plynt/pull/79), targeting `main`.
- Initial PR runs for `ade65c6a4104`: Check `41358028685`,
  Verify `41358028704`, Distribution `41358028692`, Commit `41358028686`,
  Security `41358028694`; queued at registration, not passed evidence.
- This documentation-only registration creates a new head; require all
  current-head checks again before merge. Initial run IDs are historical.
- Merge, release-please release PR, tag, GitHub release and PyPI publication:
  not performed by this execution. Version manifest remains `0.11.1`.
- Follow-up registration commit changes this release record only; see branch log
  for its hash (a commit cannot include its own hash).
