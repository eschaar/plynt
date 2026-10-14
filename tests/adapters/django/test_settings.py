"""Tests for ``plynt.adapters.django.settings``."""

import sys
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest

from plynt.adapters.django import from_django_settings
from plynt.http.settings import HTTPSettings


class DemoSettings(HTTPSettings):
    """Minimal settings model used by loader tests."""

    api_key: str = ""


class TestFromDjangoSettings:
    """Verify mapping, normalization, and validation behavior."""

    def test_builds_settings_from_uppercase_mapping(self) -> None:
        """Verify uppercase keys normalize into typed plynt settings fields."""
        settings_obj = SimpleNamespace(
            EXTERNAL_SERVICE={
                "BASE_URL": "https://api.example.test",
                "TIMEOUT_READ": 11.5,
                "API_KEY": "secret-token",
                "DEBUG": True,
                "UNRELATED_SETTING": "ignored",
            }
        )

        settings = from_django_settings(
            "EXTERNAL_SERVICE",
            DemoSettings,
            settings_obj=settings_obj,
        )

        assert settings.base_url == "https://api.example.test"
        assert settings.timeout_read == 11.5
        assert settings.api_key == "secret-token"
        assert settings.debug is True

    def test_loads_from_lazy_django_settings_import(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify fallback loading through lazy ``django.conf`` resolution.

        Args:
            monkeypatch: Fixture used to inject fake Django modules.

        """
        django_module = ModuleType("django")
        django_conf_module = ModuleType("django.conf")
        django_conf_module.__dict__["settings"] = SimpleNamespace(
            EXTERNAL_SERVICE={"BASE_URL": "https://lazy.example.test"}
        )
        django_module.__dict__["conf"] = django_conf_module

        monkeypatch.setitem(sys.modules, "django", django_module)
        monkeypatch.setitem(sys.modules, "django.conf", django_conf_module)

        settings = from_django_settings("EXTERNAL_SERVICE", HTTPSettings)

        assert settings.base_url == "https://lazy.example.test"

    def test_prefers_explicit_field_name_over_uppercase_alias(self) -> None:
        """Verify explicit field keys win over normalized uppercase aliases."""
        settings_obj = SimpleNamespace(
            EXTERNAL_SERVICE={
                "BASE_URL": "https://upper.example.test",
                "base_url": "https://lower.example.test",
            }
        )

        settings = from_django_settings(
            "EXTERNAL_SERVICE",
            HTTPSettings,
            settings_obj=settings_obj,
        )

        assert settings.base_url == "https://lower.example.test"

    def test_raises_key_error_for_missing_setting_name(self) -> None:
        """Verify missing setting blocks raise ``KeyError``."""
        settings_obj = SimpleNamespace()

        with pytest.raises(KeyError, match="MISSING_SERVICE"):
            from_django_settings(
                "MISSING_SERVICE",
                HTTPSettings,
                settings_obj=settings_obj,
            )

    def test_raises_type_error_for_non_mapping_value(self) -> None:
        """Verify non-mapping setting blocks raise ``TypeError``."""
        settings_obj = SimpleNamespace(EXTERNAL_SERVICE="https://api.example.test")

        with pytest.raises(TypeError, match="must be a mapping"):
            from_django_settings(
                "EXTERNAL_SERVICE",
                HTTPSettings,
                settings_obj=settings_obj,
            )

    def test_raises_type_error_for_non_string_mapping_key(self) -> None:
        """Verify mappings with non-string keys are rejected."""
        settings_obj = SimpleNamespace(EXTERNAL_SERVICE={1: "invalid"})

        with pytest.raises(TypeError, match="only string keys"):
            from_django_settings(
                "EXTERNAL_SERVICE",
                HTTPSettings,
                settings_obj=settings_obj,
            )

    def test_raises_type_error_for_non_settings_class(self) -> None:
        """Verify non-``BaseSettings`` classes are rejected."""
        settings_obj = SimpleNamespace(EXTERNAL_SERVICE={})

        with pytest.raises(TypeError, match="BaseSettings subclass"):
            from_django_settings(
                "EXTERNAL_SERVICE",
                cast(type[HTTPSettings], object),
                settings_obj=settings_obj,
            )
