"""Tests for public package exports in ``plynt.adapters.django``."""

import importlib

from plynt.adapters.django import (
    async_transport_from_django_settings,
    from_django_settings,
)


class TestDjangoAdapterPackage:
    """Verify package-level exports and import behavior."""

    def test_package_exports_public_names(self) -> None:
        """Verify the stable public names exported by the package."""
        module = importlib.import_module("plynt.adapters.django")

        assert module.__all__ == [
            "DjangoCacheBackend",
            "async_transport_from_django_settings",
            "from_django_settings",
            "transport_from_django_settings",
        ]

    def test_package_reexports_public_objects(self) -> None:
        """Verify package-level re-exports for core adapter entry points."""
        module = importlib.import_module("plynt.adapters.django")

        assert module.from_django_settings is from_django_settings
        assert (
            module.async_transport_from_django_settings
            is async_transport_from_django_settings
        )
        assert module.DjangoCacheBackend.__name__ == "DjangoCacheBackend"
        assert callable(module.async_transport_from_django_settings)
        assert callable(module.transport_from_django_settings)

    def test_submodules_import_without_django_installed(self) -> None:
        """Verify import-time behavior does not require Django installed."""
        importlib.import_module("plynt.adapters.django.cache")
        importlib.import_module("plynt.adapters.django.settings")
        importlib.import_module("plynt.adapters.django.transport")
