"""Tests for DRF adapter package exports."""

import importlib

from plynt.adapters.django.drf import (
    AsyncPlyntServiceMixin,
    CacheAliasesConfig,
    PlyntServiceMixin,
    RequestHeadersConfig,
    build_async_request_header_middleware,
    build_request_header_middleware,
)


class TestDrfAdapterPackage:
    """Verify DRF package export and import boundaries."""

    def test_package_exports_module_names(self) -> None:
        """Verify expected public exports from DRF adapter package."""
        module = importlib.import_module("plynt.adapters.django.drf")

        assert module.__all__ == [
            "AsyncPlyntServiceMixin",
            "CacheAliasesConfig",
            "PlyntServiceMixin",
            "RequestHeadersConfig",
            "build_async_request_header_middleware",
            "build_request_header_middleware",
            "errors",
            "headers",
            "views",
        ]

    def test_package_reexports_public_helpers(self) -> None:
        """Verify package-level re-exports for DRF helper entry points."""
        module = importlib.import_module("plynt.adapters.django.drf")

        assert module.AsyncPlyntServiceMixin is AsyncPlyntServiceMixin
        assert module.CacheAliasesConfig is CacheAliasesConfig
        assert module.PlyntServiceMixin is PlyntServiceMixin
        assert module.RequestHeadersConfig is RequestHeadersConfig
        assert (
            module.build_async_request_header_middleware
            is build_async_request_header_middleware
        )
        assert module.build_request_header_middleware is build_request_header_middleware

    def test_submodules_import_without_drf_installed(self) -> None:
        """Verify DRF adapter modules import without DRF dependency."""
        importlib.import_module("plynt.adapters.django.drf.errors")
        importlib.import_module("plynt.adapters.django.drf.headers")
        importlib.import_module("plynt.adapters.django.drf.views")
