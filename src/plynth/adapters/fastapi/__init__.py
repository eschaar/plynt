"""FastAPI framework adapter surface for Plynth.

This package provides thin FastAPI integration helpers for transport
lifecycle management, dependency wiring, request-header propagation,
and exception mapping.
"""

from plynth.adapters.fastapi.dependencies import get_client, get_transport
from plynth.adapters.fastapi.errors import (
    build_error_payload,
    create_plynth_exception_handler,
    install_plynth_exception_handlers,
    map_exception_to_fastapi_response,
)
from plynth.adapters.fastapi.headers import (
    DEFAULT_HEADER_MAP,
    DEFAULT_SENSITIVE_HEADER_DENYLIST,
    build_async_request_header_middleware,
    build_request_header_middleware,
)
from plynth.adapters.fastapi.lifespan import PlynthLifespan
from plynth.adapters.fastapi.services import build_service_dependencies, get_service

__all__ = [
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
