"""Regression tests for commit validation and automated merge policy."""

from __future__ import annotations

import os
import re
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[2]


class TestCommitWorkflow:
    def test_pr_commits_and_title_are_validated_without_branch_checks(self) -> None:
        workflow = yaml.safe_load((ROOT / ".github/workflows/commit.yml").read_text())
        step = next(
            step
            for step in workflow["jobs"]["validate"]["steps"]
            if step.get("uses", "").startswith("commit-check/commit-check-action@")
        )

        assert "if" not in step
        assert step["with"]["message"] is True
        assert step["with"]["pr-title"] is True
        assert step["with"]["branch"] is False
        # PyYAML follows YAML 1.1 and interprets the Actions "on" key as True.
        assert "edited" in workflow[True]["pull_request"]["types"]


class TestAutomergeWorkflow:
    @pytest.mark.parametrize(
        ("ecosystem", "update", "dependencies", "eligible"),
        [
            ("pip", "patch", "httpx2", True),
            ("pip", "minor", "httpx2", False),
            ("github-actions", "minor", "actions/checkout", True),
            ("github-actions", "major", "actions/checkout", False),
            ("pip", "patch", "grpcio-tools", False),
            ("pip", "patch", "httpx2, grpcio", False),
            ("pip", "patch", "protobuf, httpx2", False),
        ],
    )
    def test_eligibility_requires_manual_grpc_review(
        self,
        tmp_path: Path,
        ecosystem: str,
        update: str,
        dependencies: str,
        eligible: bool,
    ) -> None:
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/automerge.yml").read_text()
        )
        step = next(
            step
            for step in workflow["jobs"]["auto-merge"]["steps"]
            if step.get("id") == "decision"
        )
        output = tmp_path / "output"
        subprocess.run(  # noqa: S603 - Execute the repository-owned workflow script.
            [
                "/bin/bash",
                "--noprofile",
                "--norc",
                "-eo",
                "pipefail",
                "-c",
                step["run"],
            ],
            env={
                **os.environ,
                "PACKAGE_ECOSYSTEM": ecosystem,
                "UPDATE_TYPE": f"version-update:semver-{update}",
                "DEPENDENCY_NAMES": dependencies,
                "GITHUB_OUTPUT": str(output),
            },
            check=True,
            capture_output=True,
        )

        assert f"should_automerge={str(eligible).lower()}" in output.read_text()

    def test_squash_commit_uses_the_validated_pr_title(self) -> None:
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/automerge.yml").read_text()
        )
        step = next(
            step
            for step in workflow["jobs"]["auto-merge"]["steps"]
            if step.get("name") == "Enable auto-merge for eligible PR"
        )
        script = step["with"]["script"]

        assert "commitHeadline: $commitHeadline" in script
        assert "commitHeadline: context.payload.pull_request.title" in script


class TestDistributionWorkflow:
    def test_minimum_grpc_runtime_matches_the_manifest(self) -> None:
        manifest = tomllib.loads((ROOT / "pyproject.toml").read_text())
        grpc = next(
            requirement
            for requirement in manifest["project"]["optional-dependencies"]["grpc"]
            if requirement.startswith("grpcio>=")
        )
        floor = grpc.removeprefix("grpcio>=").split(",")[0]
        workflow = (ROOT / ".github/workflows/distribution.yml").read_text()
        minimum = re.search(r"'grpcio==([^']+)'", workflow)

        assert minimum is not None
        assert minimum.group(1) == floor
