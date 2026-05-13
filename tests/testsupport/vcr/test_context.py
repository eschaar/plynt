from __future__ import annotations

from collections.abc import Awaitable
from pathlib import Path
from typing import cast

import pytest

from plynth.testsupport.vcr import (
    VCRMode,
    VCRSettings,
    get_active_vcr_session,
    use_vcr,
    with_vcr,
)


class TestVCRContextAndDecorator:
    """Test suite for VCRContextAndDecorator."""

    def test_use_vcr_sets_and_resets_active_session(self, tmp_path: Path) -> None:
        """Validate use vcr sets and resets active session."""
        cassette_path = tmp_path / "ctx.yaml"
        settings = VCRSettings(mode=VCRMode.PASSTHROUGH)

        assert get_active_vcr_session() is None
        with use_vcr(cassette_path=str(cassette_path), settings=settings):
            assert get_active_vcr_session() is not None
        assert get_active_vcr_session() is None

    def test_sync_decorator_activates_session(self, tmp_path: Path) -> None:
        """Validate sync decorator activates session."""
        cassette_path = tmp_path / "sync.yaml"
        settings = VCRSettings(mode=VCRMode.PASSTHROUGH)

        @with_vcr(cassette_path=str(cassette_path), settings=settings)
        def sample() -> bool:
            """Return sample."""
            return get_active_vcr_session() is not None

        assert sample() is True

    def test_use_vcr_resolves_path_from_pytest_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Validate use vcr resolves path from pytest env."""
        settings = VCRSettings(mode=VCRMode.PASSTHROUGH)
        monkeypatch.setenv(
            "PYTEST_CURRENT_TEST",
            "tests/http/test_client.py::TestClient::test_get (call)",
        )

        with use_vcr(settings=settings) as session:
            assert "get__" in session.cassette_path

    async def test_async_decorator_activates_session(self, tmp_path: Path) -> None:
        """Validate async decorator activates session."""
        cassette_path = tmp_path / "async.yaml"
        settings = VCRSettings(mode=VCRMode.PASSTHROUGH)

        @with_vcr(cassette_path=str(cassette_path), settings=settings)
        async def sample() -> bool:
            """Return sample."""
            return get_active_vcr_session() is not None

        result = cast(Awaitable[bool], sample())
        assert await result is True

    def test_session_settings_property_is_accessible(self, tmp_path: Path) -> None:
        """Validate session settings property is accessible."""
        cassette_path = tmp_path / "ctx.yaml"
        settings = VCRSettings(mode=VCRMode.PASSTHROUGH)

        with use_vcr(cassette_path=str(cassette_path), settings=settings) as session:
            assert session.settings.mode is VCRMode.PASSTHROUGH
