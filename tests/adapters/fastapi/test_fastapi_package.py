"""Tests for public package exports in ``plynth.adapters.fastapi``."""

import importlib

from plynth.adapters.fastapi import (
    PlynthLifespan,
    build_async_request_header_middleware,
    build_error_payload,
    build_request_header_middleware,
    build_service_dependencies,
    create_plynth_exception_handler,
    get_client,
    get_service,
    get_transport,
    install_plynth_exception_handlers,
    map_exception_to_fastapi_response,
)


class TestFastAPIAdapterPackage:
    """Verify package-level exports and import behavior."""

    def test_package_exports_public_names(self) -> None:
        """Verify the stable public names exported by the package."""
        module = importlib.import_module("plynth.adapters.fastapi")

        assert module.__all__ == [
            "DEFAULT_HEADER_MAP",
            "DEFAULT_SENSITIVE_HEADER_DENYLIST",
            "PlynthLifespan",
            "build_async_request_header_middleware",
            "build_error_payload",
            "build_request_header_middleware",
            "build_service_dependencies",
            "create_plynth_exception_handler",
            "get_client",
            "get_service",
            "get_transport",
            "install_plynth_exception_handlers",
            "map_exception_to_fastapi_response",
        ]

    def test_package_reexports_public_objects(self) -> None:
        """Verify package-level re-exports for adapter entry points."""
        module = importlib.import_module("plynth.adapters.fastapi")

        assert module.PlynthLifespan is PlynthLifespan
        assert (
            module.build_async_request_header_middleware
            is build_async_request_header_middleware
        )
        assert module.build_error_payload is build_error_payload
        assert module.build_request_header_middleware is build_request_header_middleware
        assert module.build_service_dependencies is build_service_dependencies
        assert module.create_plynth_exception_handler is create_plynth_exception_handler
        assert module.get_client is get_client
        assert module.get_service is get_service
        assert module.get_transport is get_transport
        assert (
            module.install_plynth_exception_handlers
            is install_plynth_exception_handlers
        )
        assert (
            module.map_exception_to_fastapi_response
            is map_exception_to_fastapi_response
        )
