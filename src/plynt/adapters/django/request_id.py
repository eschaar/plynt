"""Wire scoped request IDs into Django responses (ADR-0040)"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from inspect import iscoroutinefunction, markcoroutinefunction
from typing import TYPE_CHECKING, cast

from plynt.base import RequestIDPolicy

if TYPE_CHECKING:  # pragma: no cover
    from django.http import HttpRequest
    from django.http.response import HttpResponseBase

__all__ = ["RequestIDMiddleware"]


class RequestIDMiddleware:
    """Scope request IDs around Django's sync or async response handler

    Place this middleware above CommonMiddleware and response-cache middleware
    so redirects, early responses, and cached responses carry the current ID.

    Args:
        policy: Validation, generation, and header configuration. Defaults to
            RequestIDPolicy; customize through a Django middleware factory.

    """

    sync_capable = True
    async_capable = True

    def __init__(
        self,
        get_response: Callable[
            [HttpRequest], HttpResponseBase | Awaitable[HttpResponseBase]
        ],
        *,
        policy: RequestIDPolicy | None = None,
    ) -> None:
        self._get_response = get_response
        self._policy = policy if policy is not None else RequestIDPolicy()
        self._async_mode = iscoroutinefunction(get_response)
        if self._async_mode:
            markcoroutinefunction(self)

    def __call__(
        self, request: HttpRequest
    ) -> HttpResponseBase | Awaitable[HttpResponseBase]:
        """Run the response handler in the detected execution mode"""
        if self._async_mode:
            return self._acall(request)
        handler = cast("Callable[[HttpRequest], HttpResponseBase]", self._get_response)
        with self._policy.scope(
            request.headers.get(self._policy.header_name)
        ) as request_id:
            response = handler(request)
            response[self._policy.header_name] = request_id
            return response

    async def _acall(self, request: HttpRequest) -> HttpResponseBase:
        """Await the response handler within a scoped request ID"""
        handler = cast(
            "Callable[[HttpRequest], Awaitable[HttpResponseBase]]", self._get_response
        )
        with self._policy.scope(
            request.headers.get(self._policy.header_name)
        ) as request_id:
            response = await handler(request)
            response[self._policy.header_name] = request_id
            return response
