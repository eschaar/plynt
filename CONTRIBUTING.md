# Contributing to Plynt

## Commit Convention

Plynt uses [Conventional Commits](https://www.conventionalcommits.org/).
Commit messages are used to automatically determine the next version number
and generate the changelog.

### Format

```text
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

### Types

| Type       | When to use                             | Version bump  |
| ---------- | --------------------------------------- | ------------- |
| `feat`     | New functionality                       | minor         |
| `feat!`    | New functionality with breaking change  | minor / major |
| `fix`      | Bug fix                                 | patch         |
| `fix!`     | Bug fix with breaking change            | minor / major |
| `perf`     | Measurable performance improvement      | patch         |
| `refactor` | Code restructuring, no behaviour change | patch         |
| `docs`     | Documentation, ADRs, comments           | patch         |
| `test`     | Tests only                              | patch         |
| `chore`    | Tooling, dependencies, CI               | patch         |
| `ci`       | CI/CD workflow changes                  | patch         |
| `style`    | Formatting, no logic change             | patch         |
| `revert`   | Revert a previous commit                | patch         |

Features produce a minor bump; other listed types normally produce a patch.
A breaking change on any type produces a minor bump while the current
version is below 1.0.0, and a major bump from 1.0.0 onward.
This uses release-please's `bump-minor-pre-major` option under
[ADR-0035](docs/architecture/adr/0035-pre-1-versioning-policy.md).

### Breaking changes

Add `!` after the type to signal a breaking change:

```text
feat!: remove timeout_seconds, replace with structured timeout fields
fix!: change Cache.get() return type
```

The `!` notation is sufficient — a `BREAKING CHANGE:` footer is optional and
only useful when you want to document migration details explicitly:

```text
feat!: remove timeout_seconds, replace with structured timeout fields

BREAKING CHANGE: Set PLYNT_TIMEOUT_READ instead of PLYNT_TIMEOUT_SECONDS.
```

Keep breaking markers and migration details even during 0.x development.
For example, a breaking change from 0.9.5 produces 0.10.0 rather than 1.0.0;
the same change from 1.0.0 produces 2.0.0.
These are policy examples, not manually selected release versions.

### Scopes

Use the module namespace as scope. Omit scope for cross-cutting changes.

| Scope        | Area                       |
| ------------ | -------------------------- |
| `base`       | `plynt.base.*`             |
| `middleware` | `plynt.middleware.*`       |
| `http`       | `plynt.http.*`             |
| `connectors` | `plynt.connectors.*`       |
| `django`     | `plynt.django.*` (future)  |
| `fastapi`    | `plynt.fastapi.*` (future) |
| `ci`         | GitHub Actions workflows   |
| `deps`       | Dependency updates         |

### Examples

```text
feat(http): add structured timeout fields to HTTPSettings
fix(auth): handle expired OAuth2 tokens in async transport
perf(core): reduce allocations in BaseSyncTransport.send()
refactor(api): extract error mapping into dedicated module
docs(adr): add ADR-0014 for logging design
test(transport): add middleware ordering tests
chore(deps): update httpx2 to 2.5
ci: upgrade actions/checkout to v5
feat!: remove timeout_seconds from HTTPSettings
```

### Enforcement

A pre-commit hook validates commit messages using
[commitlint](https://commitlint.js.org/). Messages that do not follow the
convention are rejected before the commit is created.

## Pull Requests

- Target branch: `main`
- All CI checks (lint, type check, test matrix) must pass.
- Squash merge is preferred — the PR title becomes the squash commit message,
  so follow the commit convention for PR titles too.

## Local Python Bootstrap

The supported matrix is Python 3.12-3.15 on Linux using CPython, the standard
Python implementation. Other implementations, such as PyPy, are not tested.
`.python-version` lists exact local versions, with 3.14.8 as the default.
Python 3.15 remains supported but is not the development default.
The file does not install Python; pyenv must be installed and initialized
before it can select versions or expose the executables needed by tox.

Install the compiler and libraries documented in pyenv's
[build prerequisites](https://github.com/pyenv/pyenv/wiki#suggested-build-environment).
For a new pyenv installation, use a reviewed release:

```bash
git clone --branch v2.8.9 --depth 1 https://github.com/pyenv/pyenv.git "$HOME/.pyenv"
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"
make python-install
pyenv versions
python --version
```

The clone command assumes `$HOME/.pyenv` does not already exist. For an
existing installation, update it using the
[official pyenv instructions](https://github.com/pyenv/pyenv#upgrading)
so its build definitions include 3.15.0.
Add the environment and initialization lines to your shell startup file
following pyenv's instructions; use your shell name instead of `bash`
when appropriate. Repository tooling never edits that file automatically.

`make python-install` installs all four listed interpreters, skips installed
versions, and refreshes shims. The multi-version selection exposes each
`python3.x` executable to tox; `python` selects the first available version.
Confirm 3.14.8 is selected rather than relying on fallback to another version.

Then run `make install`, `make check`, and `make test-all`.
Use `.venv` consistently for local development. An existing `.venv` does not
change Python when the version file changes. Check its interpreter first:

```bash
.venv/bin/python --version
make install PYTHON=python3.14
make check
make test-all
```

The `PYTHON` argument selects the interpreter only when `.venv` is created.
If it uses another minor version, move it outside the checkout before
running `make install` so it can be restored if needed.

CI uses `actions/setup-python` for the same minor-version matrix, not pyenv.
Poetry is not part of this repository's bootstrap or test workflow.
See [ADR-0033](docs/architecture/adr/0033-python-315-support-and-local-pyenv.md).
Python 3.11 removal and Django 6.1 requirements are recorded in
[ADR-0034](docs/architecture/adr/0034-django-6-support.md).

## Distribution and CDC code generation

Development bootstrap includes every runtime extra. Run `make install`,
then `make check` before proposing a release. The Distribution workflow
builds a wheel from the sdist and checks fresh core and optional installs;
the Verify workflow runs the complete Linux Python matrix.

The full suite enforces 100% statement coverage for the configured source
scope. Keep the existing exclusions unchanged; do not hide missing behavior
with new coverage exclusions. This is not a branch-coverage guarantee.
For a focused test run, use `pytest <test-path> --no-cov`; partial suites
are not expected to cover the entire package.

### Time-sensitive tests

Follow [ADR-0037](docs/architecture/adr/0037-deterministic-test-time.md).
Use scoped `time_machine.travel(aware_utc_datetime, tick=False)` contexts for
calendar time, including HTTP dates and JWT claims. Do not enable automatic
time freezing for the suite.

For elapsed time, request the `monotonic_clock` fixture, call
`monotonic_clock.bind("plynt.module_under_test")`, and use
`monotonic_clock.advance(seconds)`. Bind every participating module, including
the cache when testing token expiry. Bindings restore automatically after
each test and do not freeze asyncio's clock.

Do not patch the shared `time.monotonic` function. Avoid real sleeps in expiry
tests. For polling deadlines, patch the wait routine and advance the fixture
from its side effect. Keep synchronization tests separate: a wait used to
coordinate threads or yield to another task is not an expiry simulation.

Vendored Salesforce Pub/Sub Python files are generated, not hand-edited.
The development extra pins `grpcio-tools` to the version that produced
the committed output:

```bash
make salesforce-cdc-proto-generate
make salesforce-cdc-proto-verify
```

Upstream schema updates are a separate, reviewed operation: retrieve the
chosen upstream commit, verify its provenance and checksum, update the
vendored source metadata, and regenerate both Python files together.
There is no automated `salesforce-cdc-proto-update` target.
No generator is required by consumers of the installed wheel.

## Releases

Releases are fully automated. On every merge to `main`, `release-please`
maintains a release PR that updates `CHANGELOG.md` and proposes the next
version. When that PR is merged, release-please creates the Git tag and
publishes the GitHub Release.

Package versioning is derived from Git tags at build time via `setuptools_scm`
(configured in `pyproject.toml`). This repository does not use Poetry or
`poetry-dynamic-versioning`; release-please tags are the source of truth for
published package versions.

No manual version bumping or tagging is needed.

### Merge and publication safeguards

The `main` ruleset requires a pull request, resolved review threads, and the
current CI checks, including Python 3.12-3.15 and isolated distribution
installations. No second-person approval is required for the solo-maintainer
workflow. Force pushes and deletion of `main` remain blocked.

GitHub secret scanning and push protection are enabled. The `pypi`
environment permits tags matching `*.*.*`, not branches. The Publish workflow
also validates plain SemVer release tags before building or uploading.
Configure the PyPI trusted publisher for `eschaar/plynt`, workflow
`publish.yml`, and environment `pypi`. Publication is enabled for accepted
non-prerelease GitHub releases. Set `ENABLE_PYPI_PUBLISH` to `false` in the
workflow to suspend uploads without disabling build and installation checks.

### Release naming policy

- Git tags use plain SemVer: `X.Y.Z` (no `v` prefix).
- GitHub Release titles use `vX.Y.Z` for readability.
- `CHANGELOG.md` versions use `X.Y.Z` (match tags).
- Publish validation accepts only plain SemVer tags.

### Release checklist

- Ensure quality gate is green locally: `make check`.
- Confirm the PyPI trusted publisher matches the workflow and environment.
- Merge the open release-please PR into `main` (do not hand-tag).
- Confirm GitHub release exists with tag `X.Y.Z`.
- Confirm GitHub release title is `vX.Y.Z`.
- Confirm `Publish` workflow succeeded for that release.
- Confirm the intended upload policy before merging: publication is enabled
  when `ENABLE_PYPI_PUBLISH` is `true`.
