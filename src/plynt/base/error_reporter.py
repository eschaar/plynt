"""Define vendor-neutral error reporting without a default backend (ADR-0041)"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = ["ErrorReporter", "get_error_event_id"]

_EVENT_ID_ATTRIBUTE = "_plynt_error_event"
_EVENT_ID_PATTERN = re.compile(r"[A-Za-z0-9_.:-]{1,128}")


@dataclass(frozen=True)
class _ErrorEvent:
    """Hold a validated tracker receipt outside the error payload (ADR-0043)"""

    event_id: str


def _set_error_event_id(exc: Exception, event_id: str | None) -> None:
    """Replace an exception's receipt or clear it when no event was captured"""
    exc.__dict__.pop(_EVENT_ID_ATTRIBUTE, None)
    if event_id is not None:
        if (
            not isinstance(event_id, str)
            or _EVENT_ID_PATTERN.fullmatch(event_id) is None
        ):
            raise ValueError("Reporter must return a valid event ID or None")
        exc.__dict__[_EVENT_ID_ATTRIBUTE] = _ErrorEvent(event_id)


def get_error_event_id(exc: Exception) -> str | None:
    """Return the reporting ID for this exact exception, without searching causes

    No ID is generated. Unreported exceptions and failed reporting attempts
    have no ID. Custom error envelopes may explicitly include the result.
    Private reporting metadata never changes the message/code/details payload.

    """
    event = exc.__dict__.get(_EVENT_ID_ATTRIBUTE)
    return event.event_id if isinstance(event, _ErrorEvent) else None


@runtime_checkable
class ErrorReporter(Protocol):
    """Report failures with redacted context in both execution modes

    Callers supply context safe for external reporting. Implementations must
    not initialize vendor SDKs or introduce application-specific conventions.
    An event ID identifies a captured event; None means no event was captured.
    IDs use 1-128 ASCII letters, digits, underscores, dots, colons, or hyphens.
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
