"""Scope request IDs around any ASGI HTTP application (ADR-0040)"""

from __future__ import annotations

from typing import TYPE_CHECKING

from plynt.base import RequestIDPolicy

if TYPE_CHECKING:  # pragma: no cover
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

__all__ = ["RequestIDMiddleware"]


class RequestIDMiddleware:
    """Scope and echo HTTP request IDs without BaseHTTPMiddleware

    Wrap the entire application to include router redirects and outer error
    responses. WebSocket and lifespan scopes pass through unchanged.

    Args:
        policy: Validation, generation, and header configuration.
            Defaults to RequestIDPolicy.

    """

    def __init__(self, app: ASGIApp, *, policy: RequestIDPolicy | None = None) -> None:
        self._app = app
        self._policy = policy if policy is not None else RequestIDPolicy()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run HTTP scopes with a request ID and decorate response-start headers"""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        header_name = self._policy.header_name.lower().encode("ascii")
        values = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == header_name
        ]
        incoming = values[0].decode("latin-1") if len(values) == 1 else None
        with self._policy.scope(incoming) as request_id:

            async def send_with_request_id(message: Message) -> None:
                if message["type"] == "http.response.start":
                    headers = [
                        (name, value)
                        for name, value in message.get("headers", [])
                        if name.lower() != header_name
                    ]
                    headers.append((header_name, request_id.encode("ascii")))
                    message = {**message, "headers": headers}
                await send(message)

            await self._app(scope, receive, send_with_request_id)
