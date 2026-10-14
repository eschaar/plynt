"""FastAPI framework adapter surface for Plynt.

This package provides thin FastAPI integration helpers for transport
lifecycle management, dependency wiring, request-header propagation,
and exception mapping.
"""

from plynt.adapters.fastapi.dependencies import get_client, get_transport
from plynt.adapters.fastapi.errors import (
    build_error_payload,
    create_plynt_exception_handler,
    install_plynt_exception_handlers,
    map_exception_to_fastapi_response,
)
from plynt.adapters.fastapi.headers import (
    DEFAULT_HEADER_MAP,
    DEFAULT_SENSITIVE_HEADER_DENYLIST,
    build_async_request_header_middleware,
    build_request_header_middleware,
)
from plynt.adapters.fastapi.lifespan import PlyntLifespan
from plynt.adapters.fastapi.services import build_service_dependencies, get_service

__all__ = [
    "DEFAULT_HEADER_MAP",
    "DEFAULT_SENSITIVE_HEADER_DENYLIST",
    "PlyntLifespan",
    "build_async_request_header_middleware",
    "build_error_payload",
    "build_request_header_middleware",
    "build_service_dependencies",
    "create_plynt_exception_handler",
    "get_client",
    "get_service",
    "get_transport",
    "install_plynt_exception_handlers",
    "map_exception_to_fastapi_response",
]
