"""Manage framework-independent request correlation (ADR-0040)"""

from __future__ import annotations

import re
from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import uuid4

__all__ = ["RequestIDPolicy", "get_request_id"]

_current_request_id: ContextVar[str | None] = ContextVar(
    "plynt_request_id", default=None
)
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9_.:-]+")
_HEADER_NAME_PATTERN = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")


def _generate_request_id() -> str:
    """Generate a UUID hex correlation value"""
    return uuid4().hex


def get_request_id() -> str | None:
    """Return the request ID in the current execution context"""
    return _current_request_id.get()


@dataclass(frozen=True)
class RequestIDPolicy:
    """Configure validated request IDs and their scoped lifetime

    Reuse the policy across requests. The active ID belongs to an execution
    context for one inbound request and its upstream calls, not to this object.
    Independent workflow requests require separate application correlation.

    Args:
        header_name: Header used by callers to read and echo the ID.
        max_length: Maximum accepted ID length, including generated values.
        generator: Called when the inbound ID is absent, invalid, or untrusted.
            Must return a valid ID; invalid output raises ValueError.
        trust_inbound: Accept valid inbound IDs when true. Set false to always
            generate a new ID. IDs are never authorization or idempotency keys.

    """

    header_name: str = "X-Request-ID"
    max_length: int = 128
    generator: Callable[[], str] = _generate_request_id
    trust_inbound: bool = True

    def __post_init__(self) -> None:
        if not _HEADER_NAME_PATTERN.fullmatch(self.header_name):
            raise ValueError("Request ID header name must be a valid HTTP token")
        if self.max_length < 1:
            raise ValueError("Request ID max_length must be positive")
        if not callable(self.generator):
            raise TypeError("Request ID generator must be callable")

    def _is_valid(self, value: str) -> bool:
        """Check length and safe ASCII characters without logging the value"""
        return (
            0 < len(value) <= self.max_length
            and _REQUEST_ID_PATTERN.fullmatch(value) is not None
        )

    def resolve(self, incoming: str | None = None) -> str:
        """Accept a valid trusted ID or generate a replacement

        Raises:
            ValueError: If the configured generator produces an invalid ID.

        """
        if self.trust_inbound and incoming is not None and self._is_valid(incoming):
            return incoming
        generated = self.generator()
        if not isinstance(generated, str) or not self._is_valid(generated):
            raise ValueError("Request ID generator must return a valid request ID")
        return generated

    @contextmanager
    def scope(self, incoming: str | None = None) -> Generator[str, None, None]:
        """Set the ID for a block and restore the previous context on exit"""
        request_id = self.resolve(incoming)
        token = _current_request_id.set(request_id)
        try:
            yield request_id
        finally:
            _current_request_id.reset(token)
