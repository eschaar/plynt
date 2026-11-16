"""Regression tests for commit validation and automated merge policy."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.distribution.minimum_requirements import minimum_cdc_requirements

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
    @pytest.fixture
    def cdc_requirements(self) -> list[str]:
        return [
            'grpcio>=9.1,<10; extra == "grpc"',
            'protobuf>=20.2,<21; extra == "grpc"',
            'fastavro>=4.3,<5; extra == "salesforce"',
            'PyJWT>=6.4,<7; extra == "salesforce"',
        ]

    def test_minimum_profile_installs_pins_from_wheel_metadata(self) -> None:
        workflow = (ROOT / ".github/workflows/distribution.yml").read_text()

        assert "python tests/distribution/minimum_requirements.py" in workflow
        assert "-m pip install -r minimum-requirements.txt" in workflow

    @pytest.mark.parametrize(
        "grpc_requirement",
        [
            'grpcio>=9.1,<10; extra == "grpc"',
            'grpcio==9.1; extra == "grpc"',
        ],
    )
    def test_all_pins_follow_active_runtime_metadata(
        self, cdc_requirements: list[str], grpc_requirement: str
    ) -> None:
        cdc_requirements[0] = grpc_requirement
        cdc_requirements += [
            'grpcio>=99; extra == "dev"',
            'protobuf>=99; python_version < "0" and extra == "grpc"',
        ]

        assert minimum_cdc_requirements(cdc_requirements) == [
            "fastavro==4.3",
            "grpcio==9.1",
            "protobuf==20.2",
            "pyjwt==6.4",
        ]

    @pytest.mark.parametrize(
        "requirement",
        [
            "grpcio<10",
            "grpcio>9",
            "grpcio>=9,!=9",
            "grpcio>=10,<10",
            "grpcio>=9,>=9.1",
        ],
    )
    def test_unsupported_minimum_fails_explicitly(
        self, cdc_requirements: list[str], requirement: str
    ) -> None:
        cdc_requirements[0] = requirement

        with pytest.raises(ValueError, match=r"grpcio.*inclusive minimum"):
            minimum_cdc_requirements(cdc_requirements)

    def test_missing_dependency_fails_explicitly(
        self, cdc_requirements: list[str]
    ) -> None:
        cdc_requirements.pop()

        with pytest.raises(ValueError, match="Missing CDC runtime requirements: pyjwt"):
            minimum_cdc_requirements(cdc_requirements)

    def test_duplicate_active_requirement_fails_explicitly(
        self, cdc_requirements: list[str]
    ) -> None:
        cdc_requirements.append('grpcio>=9.2; extra == "salesforce"')

        with pytest.raises(
            ValueError, match="Duplicate active CDC requirement: grpcio"
        ):
            minimum_cdc_requirements(cdc_requirements)
