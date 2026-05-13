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
chore(deps): update httpx to 0.28
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
