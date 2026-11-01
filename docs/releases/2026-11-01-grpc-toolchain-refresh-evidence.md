# Post-release fixes and gRPC toolchain refresh evidence

Date: 2026-11-01
Branch: `fix/post-release-review-0120`
Main baseline: `6a47802b9276`
Architecture baseline: `27adb1e6a230`
Implementation revision: `784a445cab98`
Decision: Local implementation and ADR-0044 verification gates pass. This is
review handoff evidence, not merge or release approval.

## Scope and implementation

Applied the accepted [ADR-0044](../architecture/adr/0044-grpc-toolchain-upgrade-policy.md)
and completed four separate implementation commits:

| Commit         | Scope                                                                                                                                             |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `7b500f0d77eb` | Restore `AuthenticationError` status from serialized details without restoring a response body; add round-trip and malformed-payload tests.       |
| `352fafcb56bd` | Separate sync/async OAuth token retry observations from the parent API call; test actual terminal API attempt counts.                             |
| `f52af55e790c` | Apply PR #72's exact TruffleHog `v3.99.3` to `v3.99.7` action update.                                                                             |
| `784a445cab98` | Apply the complete gRPC 1.85 refresh: pinned generator, regenerated gRPC stub, runtime minimum, installed-minimum profile, and consumer guidance. |

PR #73's requested `grpcio-tools==1.85.0` pin was expanded into the
coordinated refresh authorized by ADR-0044. The unchanged protobuf generated
file still enforces 7.35.1, so that tested consumer floor remains unchanged.
The regenerated gRPC stub enforces `grpcio>=1.85.0`; metadata and installation
guidance now declare `grpcio>=1.85.0,<2`. Optional extras and package
boundaries are unchanged.

## Verification results

| Gate                     | Result and evidence                                                                                                                                                                                                                |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `make check`             | Pass on Python 3.14.10: 2,564 passed, 3 external tests deselected; 7,497 measured statements, 100%. Formatting, Markdown lint, Ruff, and mypy (291 files) passed.                                                                  |
| Full tox matrix          | Pass on Python 3.12.16, 3.13.18, 3.14.10, and 3.15.2. Each ran 2,564 tests with 3 external tests deselected and 100% statement coverage (7,497 statements).                                                                        |
| Generated-output drift   | `make salesforce-cdc-proto-verify` passed using `grpcio-tools==1.85.0` (`libprotoc 35.1`). Both artifacts were regenerated; `pubsub_api_pb2.py` is byte-identical and the gRPC stub's generated runtime minimum changed to 1.85.0. |
| Wheel build and metadata | `make build` built the wheel from the sdist; `twine check dist/*` passed.                                                                                                                                                          |
| Isolated wheel profiles  | Core, HTTP, gRPC, CDC, Django, DRF, FastAPI, Sentry, and CDC-minimum profiles passed on Python 3.12.16 and 3.15.2. Each environment passed `pip check`; smoke tests imported the installed wheel without codegen tooling.          |
| Exact CDC minima         | Installed-wheel profile passed on Python 3.12.16 and 3.15.2 with `grpcio==1.85.0`, `protobuf==7.35.1`, `fastavro==1.13.1`, and `PyJWT==2.15.1`.                                                                                    |
| Current CDC runtimes     | Installed-wheel profile passed on Python 3.12.16 and 3.15.2 with resolved `grpcio==1.85.1`, `protobuf==7.36.2`, `fastavro==1.13.1`, and `PyJWT==2.15.1`.                                                                           |
| Dependency checks        | Development `pip check` passed. `pip-audit --progress-spinner off` found no known vulnerabilities; it skipped the unpublished local Plynt build because it is not on PyPI.                                                         |
| Review hooks             | Commit hooks passed, including Ruff, formatting, TOML/YAML, Markdown, and gitlint checks.                                                                                                                                          |

The generator environment resolved `grpcio-tools==1.85.0`,
`grpcio==1.85.1`, and `protobuf==7.36.2`. The generated protobuf runtime
guard remained at 7.35.1; the checked-in output, not the generator's own
protobuf installation, determines the declared protobuf floor.

## Commands

```text
make check
PATH=/home/skire/.pyenv/versions/3.12.16/bin:/home/skire/.pyenv/versions/3.13.18/bin:/home/skire/.pyenv/versions/3.14.10/bin:/home/skire/.pyenv/versions/3.15.2/bin:$PATH .venv/bin/tox -q
make salesforce-cdc-proto-verify
make build
.venv/bin/twine check dist/*
.venv/bin/python -m pip check
.venv/bin/pip-audit --progress-spinner off
```

The wheel profiles used fresh virtual environments, upgraded pip to
`>=26.2,<27`, removed seeded setuptools, installed the built wheel and each
profile's extra, ran `pip check`, and executed
`tests/distribution/test_installed.py` with repository fixtures disabled.
CDC-minimum environments then installed the four exact versions listed above.

## Review and release status

No PR was merged, no commit was pushed, and no release or tag was created.
Remote CI was not run. An independent review is explicitly required before
merge. Salesforce CDC remains Experimental; these local checks do not verify
real-provider authentication, replay fidelity, or production readiness.

## Related implementation and policy

- [Generic installation requirements](../user/reference/installation.md)
- [Salesforce installation requirements](../connectors/salesforce/user/reference/installation.md)
- [Generated-code instructions](../../src/plynt/connectors/salesforce/cdc/_proto/README.md)
- [ADR-0044](../architecture/adr/0044-grpc-toolchain-upgrade-policy.md)
- [ADR-0029](../architecture/adr/0029-release-acceptance-gates-and-evidence-model.md)
