# Experimental RC Hardening Evidence

Date: 2026-10-13
Updated: 2026-10-14
Branch: `chore/experimental-rc-hardening`
Decision: Local hardening gates pass; no release or publication is approved.

This report records the current checkout, including the preceding CDC
flow-control and bitmap changes. It does not reuse the August release
evidence or assert that external provider behavior has been verified.

## Scope and Decisions

- Preserve the minimal framework-independent core and existing public names.
- Keep CDC installed through `plynt[grpc,salesforce]`.
- Include real Avro decoding in the Salesforce extra.
- Align gRPC/protobuf minima with vendored generated messages.
- Pin the development generator and verify committed output independently.
- Exercise all implemented extras in normal tests and wheel-installed tox.
- Verify core and optional profiles in isolated installed distributions.
- Keep PyPI disabled and do not create a release tag.

See [ADR-0031](../architecture/adr/0031-experimental-release-installation-contract.md)
for the accepted installation contract.

## Verified Gates

| Gate                                              | Local result                                        |
| ------------------------------------------------- | --------------------------------------------------- |
| Full suite, Python 3.14                           | 2,141 passed; 3 external tests deselected; no skips |
| Wheel-installed tox, Python 3.11                  | 2,141 passed; no failures or skips                  |
| Wheel-installed tox, Python 3.12                  | 2,141 passed; no failures or skips                  |
| Wheel-installed tox, Python 3.13                  | 2,141 passed; no failures or skips                  |
| Wheel-installed tox, Python 3.14                  | 2,141 passed; no failures or skips                  |
| Statement coverage                                | 100%; 7,124 statements, none missed                 |
| Focused coverage-path tests                       | 271 passed                                          |
| Clean wheel installs, Python 3.11 and 3.14        | All eight profiles pass                             |
| Exact CDC runtime minima                          | Pass on Python 3.11 and 3.14                        |
| Ruff formatting and lint                          | Pass                                                |
| mypy                                              | Pass; 271 files checked                             |
| Markdown and workflow checks                      | Pass                                                |
| Pinned proto regeneration                         | Exact match after import normalization              |
| Build wheel from sdist; twine metadata validation | Pass                                                |
| `pip check`                                       | Pass in development and all wheel profiles          |
| Dependency audit                                  | None known in development and CDC-minimum profiles  |

The eight wheel profiles are core, HTTP, gRPC, CDC, Django, DRF, FastAPI,
and CDC minima. Non-CDC profiles deliberately exclude the CDC-only test
case; this is not a skipped framework adapter. The full test profile has
no such skips. All full-suite runs deliberately deselect the three tests
marked `external`.

CDC minima tested together: `grpcio==1.83.1`, `protobuf==7.35.1`,
`fastavro==1.13.1`, and `PyJWT==2.15.0`.

The local runtimes are CPython 3.11.17, 3.12.15, 3.13.16, and 3.14.4.
Missing interpreters were provisioned temporarily in the session directory,
not installed into the host's executable path.

`make` is unavailable on the host. Its check components were run directly,
and tox executed the complete test matrix against installed wheels.
Raw logs and the test/coverage evidence are retained in the session workspace.
The final wheel and sdist are unpublished development artifacts, not a
versioned RC release. Their version is derived from local Git tag history,
not selected manually. Release versions and tags remain exclusively owned
by CI/CD and release-please.

## Coverage Hardening Follow-up

The October 14 follow-up adds 36 regression cases without changing
production behavior or adding coverage exclusions. They cover:

- Incomplete inherited cache and checkpoint contracts failing explicitly.
- Synchronous authentication sources and missing instance URLs.
- Missing Avro runtime hooks, nested record references, and ambiguous unions.
- Custom Pub/Sub message shapes and synchronous schema responses.
- Explicit checkpoint close, async observers, and shutdown during retry,
  response delivery, and a real local gRPC read with checkpointing.
- Optional HTTP runtime errors and transports without cleanup hooks.

`fail_under = 100` now applies to full coverage runs, including CI and tox.
The existing source scope and exclusions are unchanged. This measures
statements, not branches; generated messages, package initializers, and
existing `pragma: no cover` lines remain outside the measured scope.
The prior 43-missing-statement report is checked to fail this gate, while
the current zero-missing-statement report passes. Provider validation is
still separate from the coverage percentage.

## Commands and Reproduction

Normal repository commands:

```bash
make install
make check
make test-all
make salesforce-cdc-proto-verify
python -m pip check
pip-audit --progress-spinner off
python -m build
twine check dist/*
```

The installed-wheel test file runs independently of repository fixtures:

```bash
python -m venv wheel-env
wheel-env/bin/python -m pip install --upgrade "pip>=26.2,<27"
wheel-env/bin/python -m pip uninstall --yes setuptools
wheel-env/bin/python -m pip install "dist/<wheel>.whl[grpc,salesforce]" pytest
PLYNT_WHEEL_PROFILE=cdc wheel-env/bin/python -m pytest \
  tests/distribution/test_installed.py --noconftest \
  --import-mode=importlib -c /dev/null -p no:cacheprovider -q
```

The Distribution workflow repeats all eight profiles on Python 3.11 and
3.14. Verify repeats the full tox matrix and retains evidence even on
failure. Publish now checks clean core and CDC wheel installations before
its existing, disabled publication step. Workflow syntax was validated
locally. Remote evidence for the committed hardening revision is recorded
below; the full remote validation matrix remains outstanding.

## Remote Evidence

The hardening changes were committed and pushed on
`chore/experimental-rc-hardening`:

- `74bef3bdeeae`: CDC flow control and bitmap decoding.
- `f78247e2918ded6d37f2be0fe42a78e3411985f8`: installation hardening and
  the full-coverage gate.
- [Commit workflow run 38480835588](https://github.com/eschaar/plynt/actions/runs/38480835588)
  completed successfully for `f78247e2918ded6d37f2be0fe42a78e3411985f8`.
- `de00000c0f5bcc5d857c62da173f32edf85297f9`: documentation alignment for
  CDC scope, navigation, initial load, replay, and remote evidence.
- [Commit workflow run 38481491740](https://github.com/eschaar/plynt/actions/runs/38481491740)
  completed successfully for `de00000c0f5bcc5d857c62da173f32edf85297f9`.

This is evidence for those exact revisions, not later commits.
[PR #61](https://github.com/eschaar/plynt/pull/61) was opened against `main`.
It was subsequently merged at `68f912ce253a` after its final revision
passed Check, Verify, Distribution, Commit, and Security.
The proto-drift job initially failed because CI had no `.venv`; commit
`dd3fe9336e10` selected the active CI Python and the job passed.
This does not establish remote acceptance of later dependency refreshes.

### Main Integration Verification

The PR branch integrates `main` at `f53650085732` through a merge, without
rewriting branch history. Dependency conflicts preserve the newer httpx2,
Salesforce, and TruffleHog requirements from hardening while retaining
upstream Django, DRF, and FastAPI minima. Upstream release-please metadata
and changelog entries are retained unchanged; no release version is selected.

After conflict resolution, the local full suite passes with 2,141 tests,
three external tests deselected, and 100% statement coverage across 7,124
statements. Ruff formatting/lint, mypy, TOML/YAML hooks, and `pip check`
also pass. The installed framework versions already satisfy the merged
requirements; no dependency installation was needed for this verification.

## Dependency and Migration Notes

- CDC requires `grpcio>=1.83.1,<2` and `protobuf>=7.35.1,<8`.
  Older environments must resolve these dependencies before upgrading.
- Salesforce now installs `fastavro>=1.13.1,<2`, including for REST-only
  users. This intentionally preserves the existing installation profile.
- Salesforce requires `PyJWT>=2.15.0,<3`. The installed 2.13.0 version
  had advisories. Plynt calls JWT signing rather than decode APIs, but
  the dependency is upgraded without broad advisory exemptions.
- Development floors exclude affected urllib3 and virtualenv releases.
  Fresh wheel environments also upgrade the bundled pip, which otherwise
  retained vulnerable installer versions, and remove Python 3.11's
  vulnerable seeded setuptools. Neither setuptools nor the generator is
  needed to consume the wheel. These are tooling changes, not additions
  to the core runtime.
- Core-only users can import HTTP clients and use caller-supplied sync
  or async transports without `httpx2`. Built-in transport construction
  fails clearly when its optional backend is absent.
- The generator is `grpcio-tools==1.83.1`; consumers need only runtimes.
  The wheel includes the proto and provenance documentation.

Audit results describe the scanned installed versions, not every future
resolution permitted by the metadata. The local development build is
not published on PyPI, so the auditor skips Plynt itself; this does not
constitute a security review of Plynt's source.

## Remaining Acceptance Work

### Dependency Refresh Follow-up

The `chore/consolidate-dependabot-updates` follow-up keeps the original
hardening evidence above as a historical baseline. It consolidates the
outstanding PyJWT 2.15.1 and DRF 3.18.3 minima, then refreshes compatible
HTTP, Pydantic, cryptography, test/lint tooling, and TruffleHog versions.
Already-satisfied Dependabot proposals are not applied as downgrades.

[ADR-0032](../architecture/adr/0032-grpc-codegen-version-refresh.md)
approves `grpcio-tools==1.84.0` with `grpcio>=1.84.0,<2`.
Regeneration changes only the generated gRPC runtime version check.
The protobuf output is unchanged, preserving `protobuf>=7.35.1,<8`.
The development environment also validates protobuf 7.36.2.

The refreshed installed-wheel suites pass on Python 3.11-3.14: 2,141 tests
and 100% statement coverage per version. Clean core and exact CDC-minimum
wheel profiles pass on Python 3.11 and 3.14 with no setuptools or generator.
The updated minima are grpcio 1.84.0, protobuf 7.35.1, fastavro 1.13.1,
and PyJWT 2.15.1. Wheel-from-sdist build, twine, pinned regeneration,
Ruff format/lint, mypy, configuration hooks, and dependency consistency pass.
The installed dependency audit finds no known vulnerabilities; Plynt's
unpublished development version is skipped by that auditor.

These are local follow-up results, not remote CI evidence for this branch.
The earlier PR #61 gates do not establish acceptance of the refreshed
dependency versions. Django remains below 6, and provider validation
limitations are unchanged.

### Python 3.15 Support Follow-up

This subsection records the initial five-version follow-up. The later
Python default and Django 6.1 follow-up below replaces its support matrix
and contributor environment examples.

[ADR-0033](../architecture/adr/0033-python-315-support-and-local-pyenv.md)
extends the required Linux matrix to standard CPython 3.11-3.15 and documents
an explicit local pyenv bootstrap. The original four-version results above
remain historical evidence, not results retroactively attributed to 3.15.

The full installed-wheel tox matrix passes on CPython 3.11.17, 3.12.15,
3.13.16, 3.14.8, and 3.15.0. Each environment passes 2,141 tests with
7,124 measured statements, zero misses, and 100% statement coverage.
The three external tests remain deselected; no full-suite tests are skipped.

All eight isolated wheel profiles pass on both Python 3.11 and 3.15:
core, HTTP, gRPC, CDC, Django, DRF, FastAPI, and exact CDC minima.
The exact minima remain grpcio 1.84.0, protobuf 7.35.1, fastavro 1.13.1,
and PyJWT 2.15.1. Dependency consistency passes in all 16 environments,
without setuptools or the generator. Profiles without CDC retain the
existing empty CDC parametrization skip; the full suites exercise that test.
Wheel-from-sdist build, twine validation, `make check`, and changed-file
formatting/configuration hooks pass.
The documented `make install VENV=venv/python315 PYTHON=python3.15` bootstrap
also passes, followed by `make check VENV=venv/python315` on Python 3.15.0.
That directory uses the existing `venv/` ignore rule and preserves `.venv`.

Local compatibility testing uses session-local prebuilt interpreters.
pyenv 2.8.9 has definitions for all five listed versions. Its version
selection and shims expose Python 3.15.0 by default and all five versioned
executables. The `make python-install` target passes with these interpreters
registered as existing versions, and fails explicitly when pyenv is absent.
This verifies selection, rehash, and the skip-existing path, not source builds.
Source compilation is not tested because the host lacks a compiler.
The bootstrap documentation requires OS build prerequisites; no host pyenv
installation or shell startup configuration is changed by this verification.

These local results do not replace remote Check, Verify, and Distribution
gates for the final revision. Salesforce provider acceptance remains open.

### Python Default and Django 6.1 Follow-up

The maintainer approved Python 3.14 as the development default, removal of
Python 3.11, and a full move to Django 6.1. Python decisions are consolidated
in [ADR-0033](../architecture/adr/0033-python-315-support-and-local-pyenv.md),
which retains the original decision as history.
[ADR-0034](../architecture/adr/0034-django-6-support.md) separately records
Django 6.x support and the Python 3.12 package minimum.
These are breaking installation-contract changes, not a patch-compatible
dependency refresh. Versions and tags remain owned by CI/CD.

The final supported matrix is Python 3.12-3.15. Full installed-wheel tox
suites pass on 3.12.15, 3.13.16, 3.14.8, and 3.15.0 with Django 6.1.2,
DRF 3.18.3, and httpx2 2.13.1. Each version passes 2,144 tests with
7,124 measured statements, zero misses, and 100% statement coverage.
Three new metadata tests verify the Python minimum/classifiers and Django
requirements in both Django and DRF extras. The three external tests remain
deselected; no full-suite tests are skipped. Targeted Django, DRF, and
distribution regression tests pass: 129 tests.

All 16 isolated wheel profiles pass on Python 3.12 and 3.15, including
Django/DRF and exact CDC minima. Non-CDC profiles retain the existing empty
CDC parametrization skip; CDC profiles execute it. Installer dry runs
reject Python 3.11 and an explicit Django 5.2.18 constraint.
Wheel-from-sdist build, twine, `make check`, Ruff, mypy, formatting hooks,
dependency consistency, and pinned gRPC regeneration pass.
The installed dependency audit finds no known vulnerabilities; it skips
the unpublished Plynt development build.

The default and single-version CI jobs use Python 3.14. Local instructions
consistently use `.venv`; changing `.python-version` does not replace it.
Session-local pyenv selection confirms Python 3.14.8 as the default and
exposes all four supported interpreters. The skip-existing and rehash
bootstrap path passes. Interpreters are prebuilt for local compatibility
testing; source compilation and permanent host pyenv installation are not
performed. The existing development environment remains on Python 3.14.4
and passes its full local gate with the updated dependencies.

These results are local evidence, not remote CI acceptance. Salesforce
provider validation and release review remain required.

### Pre-1.0 Version Selection Follow-up

[ADR-0035](../architecture/adr/0035-pre-1-versioning-policy.md) approves
minor releases for breaking changes during 0.x development.
The root release-please configuration enables `bump-minor-pre-major`.
Breaking markers and migration documentation remain unchanged; neither
the release manifest nor existing tags are edited.

Local pytest verification runs the actual release-please 17.11.2 parser
and version strategy, from the 17.x line used by release-please-action v5.
All 11 checks pass: official configuration-schema validation, breaking
headers and footers before and after 1.0, normal feature/fix increments,
and the complete Django upgrade commit message.
With the current manifest at 0.9.5, that commit selects 0.10.0.
A breaking change at 1.0.0 selects 2.0.0, confirming the exception ends
automatically at the stable-version boundary.

These checks do not contact GitHub or create a release. Remote release PR
generation remains the acceptance check for the merged configuration.

### Acceptance Checklist

1. Review the dependency-refresh follow-up, then obtain successful Check,
   Verify, and Distribution evidence for its final revision. Local
   verification and the Commit workflow do not replace the full remote gates.
1. Use CI/CD and release-please for all release versions and tags. If a
   formal prerelease is needed, configure it through that automation.
   Existing publication accepts stable SemVer tags and skips prereleases;
   this hardening does not change that policy or hand-create tags.
1. Review dependency compatibility and migration notes under ADR-0027
   before accepting a named release.
1. Validate Salesforce authentication, real Avro schemas, subscription
   lifecycle, and replay against a real org.
1. Verify replay cursor fidelity: the current API exposes integer replay
   IDs while Salesforce treats them as opaque bytes. This known limitation
   is not resolved or proven safe by the local gRPC tests. Any public
   contract change requires a separate architectural decision.

The code is suitable for a reviewed experimental candidate, not a
production-readiness claim. CDC remains explicitly experimental until
the provider-specific checks pass.
