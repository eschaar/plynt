from __future__ import annotations

from pathlib import Path

import pytest

from plynt.testsupport.vcr.path import (
    DeterministicCassettePathResolver,
    build_cassette_path,
)


class TestBuildCassettePath:
    """Test suite for BuildCassettePath."""

    def test_module_without_test_prefix_in_node_id(self, tmp_path: Path) -> None:
        # Module "client.py" doesn't start with "test_" → _strip_prefix false branch
        """Validate module without test prefix in node id."""
        node_id = "tests/http/client.py::TestClient::test_get"
        p = build_cassette_path(node_id, tmp_path)
        assert p.suffix == ".yaml"
        assert "client" in str(p)

    def test_two_part_node_id(self, tmp_path: Path) -> None:
        # No class separator → len(parts) == 2
        """Validate two part node id."""
        node_id = "tests/http/test_client.py::test_get"
        p = build_cassette_path(node_id, tmp_path)
        assert p.suffix == ".yaml"
        assert "get__" in p.name

    def test_single_part_node_id(self, tmp_path: Path) -> None:
        # No :: at all → len(parts) == 1 → test_part = module_path.stem
        """Validate single part node id."""
        node_id = "tests/http/test_client.py"
        p = build_cassette_path(node_id, tmp_path)
        assert p.suffix == ".yaml"

    def test_builds_deterministic_path(self, tmp_path: Path) -> None:
        """Validate builds deterministic path."""
        node_id = (
            "tests/testsupport/vcr/test_path.py::"
            "TestBuildCassettePath::test_builds_deterministic_path"
        )
        p1 = build_cassette_path(node_id, tmp_path, extension=".yaml")
        p2 = build_cassette_path(node_id, tmp_path, extension=".yaml")
        assert p1 == p2
        assert p1.suffix == ".yaml"

    def test_raises_for_too_long_segment(self, tmp_path: Path) -> None:
        """Validate raises for too long segment."""
        long_name = "x" * 120
        node_id = f"tests/{long_name}.py::test_example"
        with pytest.raises(ValueError, match="too long"):
            build_cassette_path(node_id, tmp_path)


class TestDeterministicCassettePathResolver:
    """Test suite for DeterministicCassettePathResolver."""

    def test_resolve_explicit_path(self, tmp_path: Path) -> None:
        """Validate resolve explicit path."""
        resolver = DeterministicCassettePathResolver(cassette_root=tmp_path)
        explicit = tmp_path / "manual.yaml"
        assert resolver.resolve(cassette_path=explicit) == explicit

    def test_resolve_from_node_id_is_stable(self, tmp_path: Path) -> None:
        """Validate resolve from node id is stable."""
        resolver = DeterministicCassettePathResolver(cassette_root=tmp_path)
        node_id = "tests/http/test_client.py::TestClient::test_get"
        p1 = resolver.resolve(cassette_path=None, node_id=node_id)
        p2 = resolver.resolve(cassette_path=None, node_id=node_id)
        assert p1 == p2

    def test_resolve_from_pytest_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Validate resolve from pytest env."""
        resolver = DeterministicCassettePathResolver(cassette_root=tmp_path)
        monkeypatch.setenv(
            "PYTEST_CURRENT_TEST",
            "tests/http/test_client.py::TestClient::test_get (call)",
        )
        resolved = resolver.resolve(cassette_path=None)
        expected = resolver.from_node_id(
            "tests/http/test_client.py::TestClient::test_get"
        )
        assert resolved == expected

    def test_different_tests_do_not_collide(self, tmp_path: Path) -> None:
        """Validate different tests do not collide."""
        resolver = DeterministicCassettePathResolver(cassette_root=tmp_path)
        first = resolver.resolve(
            cassette_path=None,
            node_id="tests/http/test_client.py::TestClient::test_get",
        )
        second = resolver.resolve(
            cassette_path=None,
            node_id="tests/http/test_client.py::TestClient::test_post",
        )
        assert first != second

    def test_resolve_without_path_and_node_id_outside_pytest_raises(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Validate resolve without path and node id outside pytest raises."""
        resolver = DeterministicCassettePathResolver(cassette_root=tmp_path)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        with pytest.raises(ValueError, match="cassette_path is required"):
            resolver.resolve(cassette_path=None)
