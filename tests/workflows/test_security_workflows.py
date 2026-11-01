"""Regression tests for security-sensitive GitHub Actions configuration."""

from __future__ import annotations

import re
import shlex
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_publish_release_metadata_is_passed_as_shell_data() -> None:
    """Keep release-controlled values out of interpolated shell source."""
    workflow = (ROOT / ".github/workflows/publish.yml").read_text()

    assert "RELEASE_TAG: ${{ github.event.release.tag_name }}" in workflow
    assert "RELEASE_ACTOR: ${{ github.event.release.author.login }}" in workflow
    assert 'TAG="$RELEASE_TAG"' in workflow
    assert 'ACTOR="$RELEASE_ACTOR"' in workflow
    assert 'EXPECTED="$RELEASE_TAG"' in workflow
    assert 'TAG="${{ github.event.release.tag_name }}"' not in workflow
    assert 'ACTOR="${{ github.event.release.author.login }}"' not in workflow

    fixture = '1.2.3"; printf "must not run"; #'
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", fixture) is None


def test_publish_token_permission_is_gated_after_release_validation() -> None:
    """Keep OIDC publishing behind release checks and its protected environment."""
    workflow = (ROOT / ".github/workflows/publish.yml").read_text()
    jobs = workflow.split("jobs:", maxsplit=1)[1]
    validation_job = jobs.split("  publish:", maxsplit=1)[0]
    publish_job = jobs.split("  publish:", maxsplit=1)[1]

    assert "validate-release:" in jobs
    assert "id-token: write" not in validation_job
    assert "needs: validate-release" in publish_job
    assert "environment: pypi" in publish_job
    assert "id-token: write" in publish_job


def test_security_audit_installs_every_declared_runtime_extra() -> None:
    """Audit the base development environment and all declared runtime extras."""
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text())
    runtime_extras = set(manifest["project"]["optional-dependencies"]) - {"dev", "test"}
    workflow = (ROOT / ".github/workflows/security.yml").read_text()
    install_line = next(
        line.partition("run:")[2].strip()
        for line in workflow.splitlines()
        if "pip install -e" in line
    )
    install_args = shlex.split(install_line)
    requirement = next(arg for arg in install_args if arg.startswith(".["))
    installed_extras = set(requirement.removeprefix(".[").removesuffix("]").split(","))

    assert installed_extras == runtime_extras | {"dev"}
