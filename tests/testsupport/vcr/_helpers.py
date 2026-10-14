from __future__ import annotations

from plynt.base.request import Request
from plynt.base.response import Response


def req(method: str, url: str, content: bytes | None = None) -> Request:
    """Return req."""
    return Request(method=method, url=url, content=content)


def resp(status_code: int, body: bytes) -> Response:
    """Return resp."""
    return Response(status_code=status_code, content=body)


class SyncResponder:
    """Represent SyncResponder."""

    def __init__(self, responses: list[Response]) -> None:
        """Initialize SyncResponder."""
        self._responses = list(responses)
        self.calls = 0

    def __call__(self, request: Request) -> Response:
        """Handle call."""
        if not self._responses:
            raise AssertionError(
                f"SyncResponder called more times than expected (calls={self.calls})"
            )
        self.calls += 1
        return self._responses.pop(0)


class AsyncResponder:
    """Represent AsyncResponder."""

    def __init__(self, responses: list[Response]) -> None:
        """Initialize AsyncResponder."""
        self._responses = list(responses)
        self.calls = 0

    async def __call__(self, request: Request) -> Response:
        """Handle call."""
        if not self._responses:
            raise AssertionError(
                f"AsyncResponder called more times than expected (calls={self.calls})"
            )
        self.calls += 1
        return self._responses.pop(0)
