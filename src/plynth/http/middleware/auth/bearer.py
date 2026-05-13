"""Bearer token auth middleware for Plynth.

Provides:

- ``BearerTokenAuthMiddleware`` — sync; injects a static bearer token header.
- ``AsyncBearerTokenAuthMiddleware`` — async counterpart.

Secrets must **never** be hardcoded. Read them from environment variables
via ``HTTPSettings`` (``bearer_token`` field).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from plynth.base.middleware import AsyncMiddleware, SyncMiddleware
from plynth.base.request import Request
from plynth.base.response import Response

__all__ = [
    "AsyncBearerTokenAuthMiddleware",
    "BearerTokenAuthMiddleware",
]


class BearerTokenAuthMiddleware(SyncMiddleware):
    """Sync middleware that attaches a static bearer token.

    The token is passed at construction time and never changes. A 401
    response is not retried — static tokens cannot be refreshed.

    .. warning::
        Never hardcode the token. Read it from an environment variable
        via ``ApiSettings`` (``bearer_token`` field).

    Args:
        token: The bearer token string (without the ``Bearer `` prefix).

    Example::

        from plynth.http.middleware.auth import BearerTokenAuthMiddleware
        transport = MyTransport(middlewares=[BearerTokenAuthMiddleware("tok")])

    """

    def __init__(self, token: str) -> None:
        """Initialize BearerTokenAuthMiddleware."""
        self._token = token

    def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Response],
    ) -> Response:
        """Attach the bearer token and pass to the next handler."""
        request.headers["Authorization"] = f"Bearer {self._token}"
        return next_handler(request)


class AsyncBearerTokenAuthMiddleware(AsyncMiddleware):
    """Async middleware that attaches a static bearer token.

    Async counterpart of ``BearerTokenAuthMiddleware``.

    Args:
        token: The bearer token string (without the ``Bearer `` prefix).

    """

    def __init__(self, token: str) -> None:
        """Initialize AsyncBearerTokenAuthMiddleware."""
        self._token = token

    async def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Attach the bearer token and await the next handler."""
        request.headers["Authorization"] = f"Bearer {self._token}"
        return await next_handler(request)
