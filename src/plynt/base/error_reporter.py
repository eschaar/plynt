"""Define vendor-neutral error reporting without a default backend (ADR-0041)"""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

__all__ = ["ErrorReporter"]


@runtime_checkable
class ErrorReporter(Protocol):
    """Report failures with redacted context in both execution modes

    Callers supply context safe for external reporting. Implementations must
    not initialize vendor SDKs or introduce application-specific conventions.
    An event ID identifies a captured event; None means no event was captured.
    Reporting failures propagate to the caller rather than returning a fake ID.

    """

    def report(self, exc: Exception, context: Mapping[str, object]) -> str | None:
        """Capture an error synchronously and return its optional event ID"""
        ...  # pragma: no cover

    async def areport(
        self, exc: Exception, context: Mapping[str, object]
    ) -> str | None:
        """Capture an error asynchronously and return its optional event ID"""
        ...  # pragma: no cover
