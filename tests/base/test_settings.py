import pytest
from pydantic_settings import SettingsConfigDict

from plynt.base.settings import Settings


class TestSettings:
    """Test suite for Settings."""

    def test_debug_default_is_false(self) -> None:
        """Validate debug default is false."""
        s = Settings()
        assert s.debug is False

    def test_debug_loaded_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Validate debug loaded from env."""
        monkeypatch.setenv("DEBUG", "true")
        s = Settings()
        assert s.debug is True

    def test_is_subclassable(self) -> None:
        """Validate is subclassable."""

        class MySettings(Settings):
            """Represent MySettings."""

            api_url: str = "https://example.com"

        s = MySettings()
        assert s.api_url == "https://example.com"

    def test_env_prefix_via_subclass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Validate env prefix via subclass."""

        class MySettings(Settings):
            """Represent MySettings."""

            api_url: str = ""
            model_config = SettingsConfigDict(
                env_prefix="TEST_",
                env_file=".env",
            )

        monkeypatch.setenv("TEST_API_URL", "https://test.example.com")
        s = MySettings()
        assert s.api_url == "https://test.example.com"
