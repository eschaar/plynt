"""Observe delegated retry attempts within an optional call scope (ADR-0042)"""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace

__all__ = ["get_retry_attempts", "observe_retry_attempt", "reporting_scope"]


@dataclass(frozen=True)
class _ReportingState:
    """Hold immutable observations for one outbound reporting scope"""

    attempts: int | None = None


_state: ContextVar[_ReportingState | None] = ContextVar(
    "plynt_reporting_state", default=None
)


@contextmanager
def reporting_scope() -> Generator[None, None, None]:
    """Isolate retry observations for one logical outbound call"""
    token = _state.set(_ReportingState())
    try:
        yield
    finally:
        _state.reset(token)


def observe_retry_attempt() -> None:
    """Count a delegated attempt only when reporting is active"""
    state = _state.get()
    if state is not None:
        _state.set(replace(state, attempts=(state.attempts or 0) + 1))


def get_retry_attempts() -> int | None:
    """Return observed attempts or None when counts are unavailable"""
    state = _state.get()
    return state.attempts if state is not None else None
