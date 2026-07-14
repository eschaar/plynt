"""Tests for DRF adapter package exports."""

import importlib


class TestDrfAdapterPackage:
    """Verify DRF package export and import boundaries."""

    def test_package_exports_module_names(self) -> None:
        """Verify expected submodule exports from DRF adapter package."""
        module = importlib.import_module("plynth.adapters.django.drf")

        assert module.__all__ == ["errors", "headers", "views"]

    def test_submodules_import_without_drf_installed(self) -> None:
        """Verify DRF adapter modules import without DRF dependency."""
        importlib.import_module("plynth.adapters.django.drf.errors")
        importlib.import_module("plynth.adapters.django.drf.headers")
        importlib.import_module("plynth.adapters.django.drf.views")
