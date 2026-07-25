"""FastAPI lifespan helpers for Plynth-managed transports."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager

__all__ = [
    "PlynthLifespan",
]


class PlynthLifespan:
    """Manage one or more named transports for a FastAPI app lifespan.

    Args:
        transports: Mapping of transport names to zero-argument factory
            callables. Each factory returns either a transport object directly
            or an awaitable that resolves to one.

    """

    def __init__(
        self,
        transports: Mapping[str, Callable[[], object | Awaitable[object]]],
    ) -> None:
        """Store transport factories for startup-time construction."""
        if not transports:
            raise ValueError("transports mapping must not be empty")

        self._factories: dict[str, Callable[[], object | Awaitable[object]]] = dict(
            transports
        )

    @asynccontextmanager
    async def __call__(self, app: object) -> AsyncIterator[None]:
        """Create transports at startup and close them during shutdown."""
        state = getattr(app, "state", None)
        if state is None:
            raise RuntimeError("FastAPI app object must expose .state")

        created: dict[str, object] = {}
        state._plynth_transports = created

        try:
            for name, factory in self._factories.items():
                created[name] = await _resolve_factory_result(factory)
            yield
        finally:
            await _aclose_created_transports(created)


async def _resolve_factory_result(
    factory: Callable[[], object | Awaitable[object]],
) -> object:
    """Resolve sync or async transport factory outputs."""
    candidate = factory()
    if inspect.isawaitable(candidate):
        return await candidate
    return candidate


async def _aclose_created_transports(created: Mapping[str, object]) -> None:
    """Close transports that expose ``aclose()`` or ``close()``."""
    for _, transport in reversed(list(created.items())):
        aclose = getattr(transport, "aclose", None)
        if callable(aclose):
            await aclose()
            continue

        close = getattr(transport, "close", None)
        if callable(close):
            maybe_result = close()
            if inspect.isawaitable(maybe_result):
                await maybe_result
