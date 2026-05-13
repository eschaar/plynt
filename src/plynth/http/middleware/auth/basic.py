"""Basic auth middleware for Plynth.

Provides:

- ``BasicAuthMiddleware`` — sync; HTTP Basic auth (username + password).
- ``AsyncBasicAuthMiddleware`` — async counterpart.

Credentials must **never** be hardcoded. Read them from environment
variables via ``HTTPSettings`` (``basic_username`` / ``basic_password``).
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable

from plynth.base.middleware import AsyncMiddleware, SyncMiddleware
from plynth.base.request import Request
from plynth.base.response import Response

__all__ = [
    "AsyncBasicAuthMiddleware",
    "BasicAuthMiddleware",
]


class BasicAuthMiddleware(SyncMiddleware):
    """Sync middleware for HTTP Basic authentication.

    Encodes ``username`` and ``password`` as a static
    ``Authorization: Basic …`` header. The header is computed once at
    construction time and reused for every request. A 401 response is
    not retried — Basic credentials are static.

    .. warning::
        Never hardcode credentials. Read them from environment variables
        via ``ApiSettings`` (``basic_username`` / ``basic_password``).

    Args:
        username: The account username.
        password: The account password.

    Example::

        from plynth.http.middleware.auth import BasicAuthMiddleware
        transport = MyTransport(middlewares=[BasicAuthMiddleware("u", "p")])

    """

    def __init__(self, username: str, password: str) -> None:
        """Initialize BasicAuthMiddleware."""
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._header_value = f"Basic {encoded}"

    def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Response],
    ) -> Response:
        """Attach the Basic auth header and pass to the next handler."""
        request.headers["Authorization"] = self._header_value
        return next_handler(request)


class AsyncBasicAuthMiddleware(AsyncMiddleware):
    """Async middleware for HTTP Basic authentication.

    Async counterpart of ``BasicAuthMiddleware``.

    Args:
        username: The account username.
        password: The account password.

    """

    def __init__(self, username: str, password: str) -> None:
        """Initialize AsyncBasicAuthMiddleware."""
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._header_value = f"Basic {encoded}"

    async def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Attach the Basic auth header and await the next handler."""
        request.headers["Authorization"] = self._header_value
        return await next_handler(request)
