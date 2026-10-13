# ADR-0034: Python Default and Local Environment

**Date:** 2026-10-14
**Status:** Accepted

## Context

ADR-0033 selected Python 3.15 as the local default when adding support for
that release. The maintainer prefers Python 3.14 for day-to-day development
while continuing to test the newly released Python 3.15.

The contributor guide also introduced a second local environment convention
under `venv/`, despite the repository's established `.venv` workflow.
The maintainer requested one consistent local environment name.

## Decision

1. Select Python 3.14 as the local and single-version CI default.
   Put its exact patch version first in `.python-version`.
1. Keep Python 3.15 in the required compatibility matrix, independently of
   the development default.
1. Use `.venv` for local development examples and existing Makefile targets.
   Keep isolated wheel and tox environments separate from this editable
   development environment.
1. Explain CPython once as the standard Python implementation, then use
   Python in ordinary developer-facing prose. This does not add PyPy,
   free-threaded, debug, or other untested runtime support.
1. Preserve existing virtual environments rather than silently replacing
   them when the selected Python version changes.

This supersedes only ADR-0033's default-version choice and clarifies the
local environment convention. Other support boundaries remain unchanged
until separately recorded.

## Alternatives Considered

### Keep Python 3.15 as the default

Rejected because support for a new release does not require making it the
day-to-day development interpreter immediately.

### Document several local environment names

Rejected because alternate names make bootstrap instructions harder to
follow and conflict with the established `.venv` convention.

### Replace existing environments automatically

Rejected because interpreter selection must not delete developer state.

## Rationale

Python 3.14 remains in upstream bugfix maintenance. Python 3.15 compatibility
can be verified separately without requiring all developers to adopt it.
A single environment name reduces ambiguity without new tooling.

## Consequences

- Fast-feedback, security, commit, build, and publication jobs use 3.14.
- Compatibility jobs still test their explicit supported versions.
- Existing `.venv` interpreters retain their original patch version.
- Local bootstrap and CI defaults must be kept aligned.

## Related ADRs

- [ADR-0033](0033-python-315-support-and-local-pyenv.md): prior default.
- [ADR-0028](0028-supported-environments-and-extras-policy.md): support policy.
