# Release Verification

Date: 2026-11-01
Branch: `feature/roadmap-development`
HEAD: `7a7b96b33ebccec6ce63b7fca16c156851484843`
Comparison base: `origin/main` at `ab2d7da473d7ed0a57d625d54bd12e940e1e8dbb`
Decision: **PR handoff: OK** for the reviewed scope. Release acceptance remains
**NOK / pending** until remote CI and remaining release gates complete.

## Scope and Applicable Decisions

Verification covers the exact HEAD above against the actual `origin/main`
revision, including the public API, supported extras, and distribution tests.
The checkout was clean before verification. No source, package metadata,
release automation, version, tag, or publication was changed by this work.

Read and applied ADR-0027, ADR-0028, ADR-0029, ADR-0031, ADR-0033, ADR-0034,
ADR-0035, and ADR-0039 through ADR-0043. The current supported matrix is Linux
CPython 3.12-3.15; isolated wheel profiles are required on Python 3.12 and
3.15. Salesforce CDC remains Experimental under ADR-0031.

## Verification Results

| Criterion                        | Result                    | Current evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| -------------------------------- | ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `make check`                     | Pass                      | Python 3.14.10; formatting, markdownlint, Ruff, and mypy passed. Pytest: 2,553 passed, 3 external tests deselected; 7,481 statements, 0 missed, 100%.                                                                                                                                                                                                                                                                                                                                                          |
| Wheel-installed tox matrix       | Pass                      | Python 3.12.16, 3.13.18, 3.14.10, and 3.15.2 each passed 2,553 tests; 3 external tests deselected; 100% statement coverage (7,481-7,482 statements).                                                                                                                                                                                                                                                                                                                                                           |
| Vendored proto drift             | Pass                      | `make salesforce-cdc-proto-verify`: generated stubs match the vendored `.proto`. This does not test the live Salesforce service.                                                                                                                                                                                                                                                                                                                                                                               |
| Isolated wheel profiles          | Pass                      | Core, HTTP, gRPC, CDC, Django, DRF, FastAPI, Sentry, and CDC-minimum profiles passed on Python 3.12 and 3.15. `pip check` passed in each environment; smoke tests confirmed imports came from installed wheels without setuptools or codegen tooling.                                                                                                                                                                                                                                                          |
| Exact CDC runtime minima         | Pass                      | Both supported profile runtimes passed with `grpcio==1.84.0`, `protobuf==7.35.1`, `fastavro==1.13.1`, and `PyJWT==2.15.1`.                                                                                                                                                                                                                                                                                                                                                                                     |
| Build metadata                   | Pass                      | `python -m build` and `twine check dist/*` passed for the generated wheel and sdist. The wheel version was setuptools-scm-derived development metadata; no version was selected manually.                                                                                                                                                                                                                                                                                                                      |
| Dependency consistency and audit | Pass, scoped              | Development `pip check` and `pip-audit` passed. `pip-audit` also found no known vulnerabilities in both isolated CDC-minimum environments. It skipped the unpublished local Plynt development build because it is not on PyPI; this is not a source audit.                                                                                                                                                                                                                                                     |
| Public API comparison            | Pass with approved breaks | The source diff against actual `origin/main` adds exports and optional parameters without removing the reviewed public helper names. The intentional transport exception changes are documented by ADR-0039 and use breaking Conventional Commit markers.                                                                                                                                                                                                                                                      |
| Typed-error migration guidance   | Pass; reviewed            | Reviewed `docs/user/migrations/typed-transport-errors.md` and its links from `docs/user/README.md`, `docs/user/reference/README.md`, and `docs/user/how-to/handle-errors.md` in the current worktree. The migration accurately describes the ADR-0039 exception changes, compatibility behavior, and retry-policy distinction. Doc engineer reports markdown, link, and syntax checks passed and 396 targeted tests passed with `--no-cov`; these focused checks were not independently rerun for this review. |

### Commands

```text
make check
PATH=/home/skire/.pyenv/versions/3.12.16/bin:/home/skire/.pyenv/versions/3.13.18/bin:/home/skire/.pyenv/versions/3.14.10/bin:/home/skire/.pyenv/versions/3.15.2/bin:$PATH .venv/bin/tox -q
make salesforce-cdc-proto-verify
.venv/bin/python -m pip check
.venv/bin/pip-audit --progress-spinner off
.venv/bin/python -m build
.venv/bin/twine check dist/*
```

For isolated wheels, the built wheel was installed into fresh virtual
environments for each of the nine profiles on Python 3.12 and 3.15. Each
environment upgraded pip to `>=26.2,<27`, removed seeded setuptools, installed
the wheel plus the selected extra and pytest, ran `pip check`, and ran:

```text
PLYNT_WHEEL_PROFILE=<profile> python -m pytest \
  tests/distribution/test_installed.py --noconftest \
  --import-mode=importlib -c /dev/null -p no:cacheprovider -q
```

For the CDC-minimum profile the four exact versions above were installed, and
the smoke-test profile was set to `cdc`, matching the distribution workflow.
An initial local invocation omitted that workflow alias and failed profile
selection; the corrected invocation passed for both Python versions.

The first tox invocation could not discover the pre-provisioned pyenv
interpreters because their `bin` directories were not on `PATH`. Re-running
with the explicit interpreter paths shown above passed the complete matrix.

## Compatibility, Security, and Reliability Notes

- `TransportTimeoutError` and `TransportConnectionError` now replace raw
  backend network exception types for built-in transports. Token-response
  failures use `AuthenticationError`; its `RuntimeError` base preserves
  existing broad handlers, while response bodies are excluded from string
  and structured error output. Tests cover sync/async exception mapping,
  causes, message redaction, and the retained `RuntimeError` catch.
- Commit messages `feat(http)!: normalize transport network errors` and
  `feat(http)!: raise typed authentication errors for token failures` carry
  the required breaking markers. The exception changes are approved by
  ADR-0039 and follow the pre-1.0 policy in ADR-0035.
- Migration review: `HttpRetryPolicy`'s default classifier recognizes
  `TransportTimeoutError` and `TransportConnectionError`, plus raw `httpx2`
  network exceptions when that optional backend is installed. An explicit
  classifier replaces that default. The base, protocol-agnostic `RetryPolicy`
  instead recognizes built-in `TimeoutError`, `ConnectionError`, and `OSError`;
  it does not recognize Plynt's typed transport exceptions by default and has
  no HTTP status-code defaults. This matches the implementation in
  `src/plynt/http/policies.py`, `src/plynt/base/policies.py`, and ADR-0039.
  Migration statements on status-code retries and three total default attempts
  also match `HttpRetryPolicy`.
- The guide accurately explains `AuthenticationError`'s `TransportError` and
  `RuntimeError` bases, `status_code`, response-body handling, and the typed
  transport `__cause__` behavior. The three added entry-point links resolve
  to the migration guide. No implementation or acceptance criteria were
  changed by the documentation review.
- `make check` includes Ruff's configured security rules. The full tests
  exercise sanitized error context, event IDs, exception preservation,
  request-ID behavior, and Sentry reporting through an in-memory SDK
  transport. Dependency audit results cover installed dependencies only;
  no local source vulnerability scanner or remote secret scan was run.
- No performance benchmark or production latency observation was run.
  Optional reporting and request-ID middleware add work to request paths;
  production overhead remains unmeasured.
- No Salesforce org, live Sentry service, or external provider was contacted.
  The three tests marked `external` were deselected by repository pytest
  configuration. Salesforce authentication, real provider schemas, replay
  cursor fidelity, and long-running CDC behavior remain explicitly deferred.
  CDC must remain Experimental; these local results do not establish provider
  acceptance or production readiness.

## Sign-Off

**Local tester verification: OK** for the applicable local code, package,
matrix, proto-drift, dependency checks, and reviewed migration guidance
recorded above. The implementation evidence remains current for HEAD
`7a7b96b33ebccec6ce63b7fca16c156851484843` against
`ab2d7da473d7ed0a57d625d54bd12e940e1e8dbb`. The reviewed scope also includes
the migration and its three index/how-to links, plus the docs-only ADR-0039
and architecture-overview clarification in the current worktree; these
documentation changes are not committed.

**PR handoff: OK** from the tester for this reviewed scope. The completed
migration review closes the prior tester documentation blocker. This tester
handoff is unchanged for the implementation revisions above and the reviewed
documentation scope; it does not approve merge or publication. The architect
and designer have also returned explicit complete-scope PR handoff OK.
Product business scope is OK; the final product PR handoff remains pending
reconciliation, as recorded in the current release gate.

**Release acceptance: NOK / pending.** Remote PR/merge-group CI and the remote
secret scan have not been run; they remain later merge/publication gates, not
passes. Live Salesforce CDC remains Experimental and deferred; performance
remains unmeasured. No tests were rerun for this report clarification. Release
owns obtaining current remote evidence before merge/publication.
