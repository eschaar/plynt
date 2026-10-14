"""Deterministic cassette path helpers derived from pytest node ids."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

MAX_SEGMENT_LENGTH = 48
MAX_FILENAME_LENGTH = 64


def _strip_prefix(value: str, prefix: str) -> str:
    """Strip a prefix from ``value`` using case-insensitive matching."""
    if value.lower().startswith(prefix.lower()):
        return value[len(prefix) :]
    return value


def _slugify(value: str) -> str:
    """Convert an arbitrary string into a filesystem-safe slug."""
    cleaned = re.sub(r"\s+", "_", value.strip().lower())
    cleaned = re.sub(r"[^a-z0-9_.-]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned or "unnamed"


def _ensure_length(*, node_id: str, kind: str, value: str, limit: int) -> str:
    """Validate max length for path segments and filenames."""
    if len(value) > limit:
        msg = (
            f"Cassette {kind} too long ({len(value)}>{limit}): {value!r}. "
            f"node_id={node_id!r}"
        )
        raise ValueError(msg)
    return value


def build_cassette_path(
    node_id: str,
    cassette_root: Path,
    extension: str = ".yaml",
) -> Path:
    """Build a deterministic cassette path from a pytest node id.

    Path layout:
    - ``<root>/<suite>/<module>/<class>/<test>__<hash>.yaml``
    - ``<root>/<suite>/<domain>/<module>/<class>/<test>__<hash>.yaml``
      when the test module is nested one directory deeper, for example
      ``tests/connectors/salesforce/test_smoke.py``.
    """
    parts = node_id.split("::")
    module_path = Path(parts[0])

    suite_raw = module_path.parts[1] if len(module_path.parts) > 1 else "root"
    suite = _ensure_length(
        node_id=node_id,
        kind="segment[suite]",
        value=_slugify(suite_raw),
        limit=MAX_SEGMENT_LENGTH,
    )

    module_raw = _strip_prefix(module_path.stem, "test_")
    module_name = _ensure_length(
        node_id=node_id,
        kind="segment[module]",
        value=_slugify(module_raw),
        limit=MAX_SEGMENT_LENGTH,
    )

    domain: str | None = None
    # Example: tests/connectors/salesforce/test_smoke.py
    # parts[1] -> connectors (suite), parts[2] -> salesforce (domain)
    if len(module_path.parts) > 3:
        domain_raw = module_path.parts[2]
        domain = _ensure_length(
            node_id=node_id,
            kind="segment[domain]",
            value=_slugify(domain_raw),
            limit=MAX_SEGMENT_LENGTH,
        )

    class_name: str | None = None
    test_part: str
    if len(parts) >= 3:
        class_name = _ensure_length(
            node_id=node_id,
            kind="segment[class]",
            value=_slugify(_strip_prefix(parts[1], "Test")),
            limit=MAX_SEGMENT_LENGTH,
        )
        test_part = parts[2]
    elif len(parts) == 2:
        test_part = parts[1]
    else:
        test_part = module_path.stem

    test_base = test_part.split("[", 1)[0]
    test_name = _ensure_length(
        node_id=node_id,
        kind="segment[test]",
        value=_slugify(_strip_prefix(test_base, "test_")),
        limit=MAX_SEGMENT_LENGTH,
    )

    path = cassette_root / suite / module_name
    if domain:
        path = cassette_root / suite / domain / module_name
    if class_name:
        path = path / class_name

    suffix = hashlib.sha256(node_id.encode("utf-8")).hexdigest()[:8]
    filename = _ensure_length(
        node_id=node_id,
        kind="filename",
        value=f"{test_name}__{suffix}{extension}",
        limit=MAX_FILENAME_LENGTH,
    )
    return path / filename


@dataclass(frozen=True)
class DeterministicCassettePathResolver:
    """Resolve explicit or deterministic cassette paths.

    When ``cassette_path`` is provided, it is used directly.
    When absent, path is deterministically derived from a pytest node id.
    """

    cassette_root: Path = Path("tests/_mock/cassettes")
    extension: str = ".yaml"

    @staticmethod
    def node_id_from_pytest_current_test(pytest_current_test: str) -> str:
        """Extract pytest node id from ``PYTEST_CURRENT_TEST`` value."""
        return pytest_current_test.split(" (", 1)[0].strip()

    def from_node_id(self, node_id: str) -> Path:
        """Build deterministic path from node id using configured root."""
        return build_cassette_path(node_id, self.cassette_root, self.extension)

    def resolve(
        self,
        *,
        cassette_path: str | Path | None,
        node_id: str | None = None,
        pytest_current_test: str | None = None,
    ) -> Path:
        """Resolve a cassette path from explicit path or deterministic node id."""
        if cassette_path is not None:
            return Path(cassette_path)

        effective_node_id = node_id
        if effective_node_id is None:
            raw_current_test = pytest_current_test or os.getenv("PYTEST_CURRENT_TEST")
            if raw_current_test:
                effective_node_id = self.node_id_from_pytest_current_test(
                    raw_current_test
                )

        if effective_node_id is None:
            msg = (
                "cassette_path is required outside pytest, or provide node_id "
                "for deterministic path resolution"
            )
            raise ValueError(msg)

        return self.from_node_id(effective_node_id)
