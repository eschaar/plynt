"""Contract tests for generic gRPC settings behavior."""

from __future__ import annotations

import pytest

from plynth.grpc.settings import GrpcSettings


class TestGrpcSettingsContract:
    """Verify defaults and environment loading contracts."""

    def test_defaults_are_stable(self) -> None:
        """Validate default values for unset fields."""
        settings = GrpcSettings()

        assert settings.target == ""
        assert settings.timeout == 30.0
        assert settings.secure is True
        assert settings.metadata == {}

    def test_env_prefix_is_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Validate fields resolve from the PLYNTH_GRPC env namespace."""
        monkeypatch.setenv("PLYNTH_GRPC_TARGET", "dns:///env.grpc.local:443")
        monkeypatch.setenv("PLYNTH_GRPC_TIMEOUT", "7.25")
        monkeypatch.setenv("PLYNTH_GRPC_SECURE", "false")

        settings = GrpcSettings()

        assert settings.target == "dns:///env.grpc.local:443"
        assert settings.timeout == 7.25
        assert settings.secure is False
