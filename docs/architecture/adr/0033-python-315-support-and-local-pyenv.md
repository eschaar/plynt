# ADR-0033: Python Support and Local pyenv Bootstrap

**Date:** 2026-10-14
**Status:** Accepted

## Approved Follow-up

On 2026-10-14, the maintainer approved consolidating the Python decisions
from this unmerged change into this record. The original accepted decision
is retained below for traceability; the following approved changes describe
the current Python contract.

1. Support Python 3.12, 3.13, 3.14, and 3.15 on Linux. The Python 3.12
   minimum follows the Django decision in
   [ADR-0034](0034-django-6-support.md), replacing the original 3.11 minimum.
1. Use Python 3.14 as the local and single-version CI default, rather than
   newly released 3.15. Keep 3.15 in the required compatibility matrix.
1. Keep four exact patch versions in `.python-version`, with the 3.14
   version first. Remove 3.11 from classifiers, tox, and CI.
1. Test all runtime extras on Python 3.12-3.15 and isolated wheel profiles
   on the oldest and newest supported versions, 3.12 and 3.15.
1. Use `.venv` consistently for local development. Isolated distribution
   and tox environments remain separate from the editable installation.
1. CPython means the standard Python implementation, as opposed to PyPy.
   Use Python in ordinary prose without implying support for other
   implementations, free-threaded builds, or debug variants.
1. Keep explicit pyenv provisioning and pip/setuptools/tox tooling.
   Never replace existing environments or edit shell startup automatically.
1. Raising the minimum interpreter does not require migrating existing
   generic APIs to PEP 695 syntax. Keep that refactor out of this change.

Python 3.14 and 3.15 are in upstream bugfix maintenance; 3.12 and 3.13
receive security fixes. Python 3.10 is end of life and remains unsupported.
Security-only maintenance is not itself an end-of-life status.

### Alternatives for the Follow-up

- Keep 3.15 as the default: rejected because support does not require
  immediate adoption as the day-to-day development interpreter.
- Document multiple local environment names: rejected in favor of `.venv`.
- Replace existing environments automatically: rejected to preserve
  developer state.

### Follow-up Consequences

- The current full compatibility matrix contains four Python versions.
- Fast-feedback, security, commit, build, and publication jobs use 3.14.
- Existing `.venv` environments keep their original interpreter.
- Python 3.11 removal is a breaking installation change governed by
  ADR-0034 and the existing release acceptance policy.
- The five-version and 3.15-default choices below are historical only.

## Original Accepted Decision

The following sections preserve the original decision before the approved
follow-up. They are not the current support matrix or default selection.

### Context

ADR-0028 permits a fifth supported Python version when the newest stable
release is available. CPython 3.15.0 is released, and the maintainer approved
adding it to the Linux support matrix.

The repository already has a multi-version `.python-version`, but no
documented pyenv bootstrap. That file alone neither installs Python nor
supplies missing interpreters to tox. Local verification needed temporary
interpreter provisioning, while CI uses `actions/setup-python`.

### Decision

1. Support standard CPython 3.11, 3.12, 3.13, 3.14, and 3.15 on Linux.
   This does not add free-threaded, debug, PyPy, or other OS variants.
1. Add 3.15 to the required full installed-wheel tox and CI test matrix.
1. Run isolated distribution profiles on the oldest and newest supported
   versions, 3.11 and 3.15, including exact CDC runtime minima.
1. Use pyenv as the documented local interpreter manager. Keep five exact
   CPython patch versions in `.python-version`, with 3.15.0 first.
1. Add an explicit `make python-install` target that requires installed
   pyenv and installs missing versions listed in `.python-version`.
   Do not silently install pyenv or modify developer shell configuration.
1. Keep CI provisioning through `actions/setup-python`; pyenv is not a
   runtime dependency or a new CI dependency.
1. Preserve pip, setuptools, and tox as the development/build workflow.
   Poetry is not required for installation, interpreter management, or tests.

This extends ADR-0028's baseline to five versions and replaces ADR-0031's
four-version matrix. Their other support and installation decisions remain.

### Alternatives Considered

#### Local-only Python 3.15

Rejected because the maintainer requested official support, which requires
CI and installed-distribution acceptance rather than an optional local test.

#### Keep the version file without a bootstrap

Rejected because it leaves developers expecting interpreters that are not
installed and makes the local tox matrix unreliable.

#### Require pyenv in CI and package installations

Rejected because setup-python already supplies CI interpreters, and
consumers need Python itself rather than a specific interpreter manager.

### Rationale

One explicit local bootstrap closes the gap without changing package
dependencies or introducing a second dependency-management workflow.
The existing tox and wheel tests verify Python compatibility separately
from how an interpreter is installed.

### Consequences

- Required CI expands from four to five full test environments.
- Python 3.15 wheels must exist or dependencies must build successfully,
  including the exact CDC minimum profile.
- Local pyenv source builds require OS compiler and development libraries.
  Installing those prerequisites remains an explicit developer operation.
- Existing virtual environments retain their original interpreter.
  Changing `.python-version` does not upgrade an already-created `.venv`.
- Python support does not establish real Salesforce provider correctness.

## Related ADRs

- [ADR-0028](0028-supported-environments-and-extras-policy.md): support policy.
- [ADR-0031](0031-experimental-release-installation-contract.md): wheel gates.
- [ADR-0032](0032-grpc-codegen-version-refresh.md): pinned CDC code generation.
- [ADR-0034](0034-django-6-support.md): Django 6.x and Python 3.12 minimum.
