"""Derive the CDC minimum-runtime pins from installed wheel metadata"""

from __future__ import annotations

import sys
from importlib import metadata

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def minimum_cdc_requirements(requirements: list[str]) -> list[str]:
    """Return exact CDC pins from active runtime requirements

    Raises:
        ValueError: A dependency is missing, duplicated, or lacks a supported
            inclusive minimum that satisfies its complete specifier.
    """
    dependencies = {"grpcio", "protobuf", "fastavro", "pyjwt"}
    pins: dict[str, str] = {}
    for requirement_text in requirements:
        requirement = Requirement(requirement_text)
        name = canonicalize_name(requirement.name)
        if name not in dependencies:
            continue
        if requirement.marker is not None and not any(
            requirement.marker.evaluate({"extra": extra})
            for extra in ("grpc", "salesforce")
        ):
            continue
        if name in pins:
            raise ValueError(f"Duplicate active CDC requirement: {name}")
        minima = [
            specifier.version
            for specifier in requirement.specifier
            if specifier.operator in {">=", "=="} and "*" not in specifier.version
        ]
        if len(minima) != 1 or not requirement.specifier.contains(
            minima[0], prereleases=True
        ):
            raise ValueError(
                f"{name} must declare one supported inclusive minimum: "
                f"{requirement.specifier}"
            )
        pins[name] = f"{name}=={minima[0]}"

    missing = dependencies - pins.keys()
    if missing:
        raise ValueError(
            f"Missing CDC runtime requirements: {', '.join(sorted(missing))}"
        )
    return [pins[name] for name in sorted(pins)]


if __name__ == "__main__":
    sys.stdout.write(
        "\n".join(minimum_cdc_requirements(metadata.requires("plynt") or [])) + "\n"
    )
