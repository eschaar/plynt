"""Regression tests for the verification workflow's failure propagation."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("step", ["Tox env listing (evidence)", "Test via tox"])
def test_tox_evidence_pipeline_preserves_failure(step: str) -> None:
    """Propagate a producer failure through the configured Actions shell"""
    workflow = (ROOT / ".github/workflows/verify.yml").read_text()
    block = workflow.split(f"- name: {step}\n", maxsplit=1)[1].split(
        "- name:", maxsplit=1
    )[0]
    shell = re.search(r"^\s+shell: (\w+)$", block, re.MULTILINE)
    assert shell is not None
    assert shell.group(1) == "bash"
    assert "| tee evidence/tox-" in block

    # Match Actions' explicit bash template, not the implicit Linux shell.
    result = subprocess.run(
        [
            "/bin/bash",
            "--noprofile",
            "--norc",
            "-eo",
            "pipefail",
            "-c",
            "false | tee /dev/null",
        ],
        check=False,
        capture_output=True,
    )
    assert result.returncode == 1
