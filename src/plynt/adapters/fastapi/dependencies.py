"""FastAPI dependency helpers for resolving Plynt transports and clients."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import Request  # pyright: ignore[reportMissingImports]

__all__ = [
    "get_client",
    "get_transport",
]

ClientT = TypeVar("ClientT")


def get_transport(name: str) -> Callable[[Request], object]:
    """Return a FastAPI dependency that resolves one named app transport."""

    def _dependency(request: Request) -> object:
        transports = _resolve_transport_map(request)
        if name not in transports:
            raise RuntimeError(f"Plynt transport '{name}' is not registered")
        return transports[name]

    return _dependency


def get_client(
    transport_name: str,
    client_class: type[ClientT],
    /,
    **client_kwargs: object,
) -> Callable[[Request], ClientT]:
    """Return a FastAPI dependency that builds one client from a transport."""

    def _dependency(request: Request) -> ClientT:
        transport = get_transport(transport_name)(request)
        return client_class(transport=transport, **client_kwargs)  # type: ignore[call-arg]

    return _dependency


def _resolve_transport_map(request: Request) -> dict[str, object]:
    """Resolve the app-scoped Plynt transport map from request state."""
    app = getattr(request, "app", None)
    state = getattr(app, "state", None)
    transports = getattr(state, "_plynt_transports", None)

    if not isinstance(transports, dict):
        raise RuntimeError(
            "Plynt transports are not initialized on app.state. "
            "Configure FastAPI with PlyntLifespan first."
        )

    return transports
