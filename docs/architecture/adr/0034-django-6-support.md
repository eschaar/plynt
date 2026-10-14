# ADR-0034: Django 6.x Support and Python 3.12 Minimum

**Date:** 2026-10-14
**Status:** Accepted

## Context

The maintainer requested Django 6.1 and explicitly approved dropping
Python 3.11 support rather than retaining an older Django line.
Django 6.1.2 requires Python 3.12 or newer. Requiring it unconditionally
while advertising the previous Python 3.11 matrix would break installation.

The Python default, tested versions, and local bootstrap are maintained
together in ADR-0033. This record owns the Django dependency boundary and
the package-wide minimum interpreter required by that boundary.

## Decision

1. Require Python 3.12 or newer for the entire package, not just Django
   extras. Implement interpreter selection and the matrix under ADR-0033.
1. Require `django>=6.1.2,<7` in both Django and DRF extras.
   Do not retain a Python-conditional Django 5.2 fallback.
1. Keep `djangorestframework>=3.18.3,<4` and `httpx2>=2.13.1`.
   httpx2 2.13.1 is already the latest verified release.
1. Test Django and DRF behavior on every Python version in ADR-0033,
   including their isolated wheel installation profiles.
1. Keep framework dependencies optional. Core, transport responsibilities,
   sync/async design, and all other extra boundaries remain unchanged.
1. Treat Python 3.11 and Django 5.2 removal as breaking installation changes.
   Use a breaking Conventional Commit and migration documentation.
   CI/CD and release-please continue to own version numbers and tags.

This supersedes the original Python 3.11 minimum in ADR-0028 and ADR-0031.
ADR-0033 records the approved Python follow-up for this dependency decision.
Their other decisions remain unchanged.

## Alternatives Considered

### Allow both Django 5.2 and 6.1

Rejected by the maintainer in favor of one current Django line.
Although backward compatible, it would require maintaining both contracts.

### Use Django 5.2 only on Python 3.11

Rejected because interpreter-conditional framework versions would increase
the installation and testing surface the maintainer wants to simplify.

### Drop Python 3.11 only for Django extras

Rejected because the maintainer chose to drop it for the entire package.
That makes package metadata and all test profiles share one minimum.

## Rationale

A Python 3.12 minimum matches Django 6.1's interpreter requirement and avoids
silent dependency fallbacks. Four explicit Python versions preserve useful
compatibility coverage without testing an unsupported installation profile.
The existing HTTP backend is already current; no new dependency is needed.

## Consequences

- Python 3.11 consumers cannot install the new release.
- Django/DRF users must upgrade their application to Django 6.1 first.
- The breaking release must pass ADR-0027 and ADR-0029 acceptance gates.
- Wheel metadata tests verify the interpreter and Django requirements.
- Django and DRF behavior must pass tests with the upgraded framework.
- Local evidence does not replace remote gates or Salesforce-org validation.

## Related ADRs

- [ADR-0027](0027-public-api-compatibility-and-deprecation-policy.md):
  breaking compatibility policy.
- [ADR-0028](0028-supported-environments-and-extras-policy.md): prior matrix.
- [ADR-0031](0031-experimental-release-installation-contract.md): wheel gates.
- [ADR-0033](0033-python-315-support-and-local-pyenv.md): Python contract.
