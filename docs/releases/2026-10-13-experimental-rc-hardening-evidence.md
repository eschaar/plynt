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
- Keep CDC installed through `plynth[grpc,salesforce]`.
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
PLYNTH_WHEEL_PROFILE=cdc wheel-env/bin/python -m pytest \
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
- [Commit workflow run 38480835588](https://github.com/eschaar/plynth/actions/runs/38480835588)
  completed successfully for `f78247e2918ded6d37f2be0fe42a78e3411985f8`.
- `de00000c0f5bcc5d857c62da173f32edf85297f9`: documentation alignment for
  CDC scope, navigation, initial load, replay, and remote evidence.
- [Commit workflow run 38481491740](https://github.com/eschaar/plynth/actions/runs/38481491740)
  completed successfully for `de00000c0f5bcc5d857c62da173f32edf85297f9`.

This is evidence for those exact revisions, not later documentation commits.
At this documentation update, no PR exists for the branch. Check, Verify,
and Distribution still need remote evidence through their configured
triggers; the successful Commit workflow does not replace those gates.

## Dependency and Migration Notes

- CDC requires `grpcio>=1.83.1,<2` and `protobuf>=7.35.1,<8`.
  Older environments must resolve these dependencies before upgrading.
- Salesforce now installs `fastavro>=1.13.1,<2`, including for REST-only
  users. This intentionally preserves the existing installation profile.
- Salesforce requires `PyJWT>=2.15.0,<3`. The installed 2.13.0 version
  had advisories. Plynth calls JWT signing rather than decode APIs, but
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
not published on PyPI, so the auditor skips Plynth itself; this does not
constitute a security review of Plynth's source.

## Remaining Acceptance Work

1. Open and review a PR, then obtain successful Check, Verify, and
   Distribution evidence for the final revision. Local verification and
   the successful Commit workflow do not replace the full remote gates.
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
