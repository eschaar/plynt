"""FastAPI service dependency helpers for Plynth."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypeVar, cast

from fastapi import Request  # pyright: ignore[reportMissingImports]

from plynth.adapters.fastapi.dependencies import get_transport

__all__ = [
    "build_service_dependencies",
    "get_service",
]

ServiceT = TypeVar("ServiceT")


def build_service_dependencies(
    *,
    transport_name: str,
    factories: Mapping[str, Callable[[object], object]],
    cache: bool = True,
) -> dict[str, Callable[[Request], object]]:
    """Build a dependency map for multiple named services.

    This helper is useful for router setup where one endpoint group needs
    several service dependencies that all share the same named transport.

    Args:
        transport_name: Name of the registered app transport to resolve.
        factories: Service factories keyed by service dependency name.
        cache: Cache built services on ``request.state`` for one request.

    Returns:
        Mapping from service name to FastAPI dependency callables.

    """
    return {
        service_name: get_service(
            service_name,
            transport_name=transport_name,
            factory=factory,
            cache=cache,
        )
        for service_name, factory in factories.items()
    }


def get_service(
    service_name: str,
    *,
    transport_name: str,
    factory: Callable[[object], ServiceT],
    cache: bool = True,
) -> Callable[[Request], ServiceT]:
    """Return a dependency that builds one named service from a transport.

    Args:
        service_name: Service key used for optional request-level caching.
        transport_name: Name of the registered app transport to resolve.
        factory: Callable that accepts one transport and returns a service.
        cache: Cache built service on ``request.state`` for one request.

    Returns:
        FastAPI dependency callable that returns a service instance.

    """

    def _dependency(request: Request) -> ServiceT:
        transport = get_transport(transport_name)(request)
        if not cache:
            return factory(transport)

        service_cache = _resolve_service_cache(request)
        if service_name in service_cache:
            return cast(ServiceT, service_cache[service_name])

        service = factory(transport)
        service_cache[service_name] = service
        return service

    return _dependency


def _resolve_service_cache(request: Request) -> dict[str, Any]:
    """Resolve or initialize service cache on FastAPI request state."""
    app = getattr(request, "app", None)
    state = getattr(app, "state", None)
    if state is None:
        raise RuntimeError("FastAPI request app object must expose .state")

    cache = getattr(state, "plynth_services", None)
    if not isinstance(cache, dict):
        cache = {}
        cast(Any, state).plynth_services = cache

    return cache
