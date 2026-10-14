# Contributing to Plynth

## Commit Convention

Plynth uses [Conventional Commits](https://www.conventionalcommits.org/).
Commit messages are used to automatically determine the next version number
and generate the changelog.

### Format

```text
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

### Types

| Type       | When to use                             | Version bump |
| ---------- | --------------------------------------- | ------------ |
| `feat`     | New functionality                       | minor        |
| `feat!`    | New functionality with breaking change  | major        |
| `fix`      | Bug fix                                 | patch        |
| `fix!`     | Bug fix with breaking change            | major        |
| `perf`     | Measurable performance improvement      | patch        |
| `refactor` | Code restructuring, no behaviour change | patch        |
| `docs`     | Documentation, ADRs, comments           | patch        |
| `test`     | Tests only                              | patch        |
| `chore`    | Tooling, dependencies, CI               | patch        |
| `ci`       | CI/CD workflow changes                  | patch        |
| `style`    | Formatting, no logic change             | patch        |
| `revert`   | Revert a previous commit                | patch        |

Every commit type produces at least a patch bump. Only `feat`, `fix`, and
their `!` variants affect the minor and major version.

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

BREAKING CHANGE: Set PLYNTH_TIMEOUT_READ instead of PLYNTH_TIMEOUT_SECONDS.
```

### Scopes

Use the module namespace as scope. Omit scope for cross-cutting changes.

| Scope        | Area                        |
| ------------ | --------------------------- |
| `base`       | `plynth.base.*`             |
| `middleware` | `plynth.middleware.*`       |
| `http`       | `plynth.http.*`             |
| `connectors` | `plynth.connectors.*`       |
| `django`     | `plynth.django.*` (future)  |
| `fastapi`    | `plynth.fastapi.*` (future) |
| `ci`         | GitHub Actions workflows    |
| `deps`       | Dependency updates          |

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

### Release naming policy

- Git tags use plain SemVer: `X.Y.Z` (no `v` prefix).
- GitHub Release titles use `vX.Y.Z` for readability.
- `CHANGELOG.md` versions use `X.Y.Z` (match tags).
- Publish validation accepts only plain SemVer tags.

### Release checklist

- Ensure quality gate is green locally: `make check`.
- Merge the open release-please PR into `main` (do not hand-tag).
- Confirm GitHub release exists with tag `X.Y.Z`.
- Confirm GitHub release title is `vX.Y.Z`.
- Confirm `Publish` workflow succeeded for that release.
- Keep `ENABLE_PYPI_PUBLISH` disabled unless you intentionally publish to PyPI.
