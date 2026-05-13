"""Log filters for Plynth services.

Provides reusable ``logging.Filter`` subclasses that can be attached to any
Python log handler, independent of the Plynth transport or middleware layer:

- ``ThrottleLogs`` — suppresses repeated log records after a configurable
  per-window limit, preventing log- and Sentry-flooding from noisy upstreams.
- ``ExceptionInfoFilter`` — injects active exception context into records
  that were emitted without it.
- ``PlynthHTTPFilter`` — convenience subclass of ``ThrottleLogs``
  pre-configured for the ``plynth.http`` logger with sensible defaults.
"""

from __future__ import annotations

import logging
import sys
import threading
from re import Pattern

__all__ = [
    "ExceptionInfoFilter",
    "PlynthHTTPFilter",
    "ThrottleLogs",
]


class ThrottleLogs(logging.Filter):
    """Suppress repeated log records once a per-window count limit is reached.

    Tracks records that match an optional logger-name prefix and/or message
    pattern. Once the running count within the active time window reaches
    ``limit``, further matching records are suppressed. The counter resets
    automatically when the first record of a new window arrives.

    Records that do **not** match the ``name`` or ``pattern`` constraints
    always pass through — the filter only acts on records it explicitly
    targets.

    This filter is thread-safe.

    Args:
        name: Logger name prefix to target. When set, only records whose
            ``record.name`` starts with this value are counted and
            potentially suppressed. Records from all other loggers pass
            through unconditionally. When ``None``, records from every
            logger are counted.
        limit: Maximum number of matching records allowed within a single
            window before suppression begins. Use ``0`` to suppress all
            matching records from the very first one. Defaults to ``60``.
        pattern: Optional compiled regular expression. When provided, only
            records whose formatted message matches this pattern are counted
            and subject to suppression. Non-matching records pass through
            unconditionally.
        window: Duration of the rolling time window in seconds. The counter
            resets when a matching record arrives more than ``window`` seconds
            after the start of the current window. Defaults to ``3600``
            (one hour).

    Example::

        import logging
        from plynth.log import ThrottleLogs

        # Allow at most 10 transport warnings per hour; suppress the rest.
        handler = logging.StreamHandler()
        handler.addFilter(ThrottleLogs(name="plynth.http", limit=10))

    """

    def __init__(
        self,
        name: str | None = None,
        *,
        limit: int = 60,
        pattern: Pattern[str] | None = None,
        window: int = 3600,
    ) -> None:
        # Pass an empty name to the base class so all records reach filter().
        # We perform our own name-prefix matching below.
        """Initialize ThrottleLogs."""
        super().__init__("")
        self._target_name = name
        self._limit = limit
        self._pattern = pattern
        self._window = window
        self._count: int = 0
        # Initialised to 0.0 so the very first record always starts a new
        # window (record.created is a Unix timestamp, always >> window).
        self._window_start: float = 0.0
        self._lock = threading.Lock()

    def filter(self, record: logging.LogRecord) -> bool:
        """Return ``False`` to suppress the record once the limit is reached.

        Args:
            record: The log record to evaluate.

        Returns:
            ``True`` to emit the record; ``False`` to suppress it.

        """
        # Records from non-targeted loggers are never counted or suppressed.
        if self._target_name and not record.name.startswith(self._target_name):
            return True

        # Records whose message does not match the pattern pass through.
        if self._pattern and not self._pattern.search(record.getMessage()):
            return True

        with self._lock:
            # Start a new window when the current record falls outside the
            # active window interval.
            if record.created - self._window_start >= self._window:
                self._window_start = record.created
                self._count = 0

            self._count += 1
            return self._count <= self._limit


class ExceptionInfoFilter(logging.Filter):
    """Attach active exception info to log records that omit it.

    Some loggers emit ``WARNING`` or ``ERROR`` records without ``exc_info``
    even when called from within an active ``except`` block. This filter
    checks ``sys.exc_info()`` and, when an exception is active, attaches
    it to the record so that log formatters and error-tracking tools (e.g.
    Sentry) can include the full traceback.

    Records that already carry exception information are left untouched.
    This filter never suppresses records — it always returns ``True``.

    Example::

        import logging
        from plynth.log import ExceptionInfoFilter

        handler = logging.StreamHandler()
        handler.addFilter(ExceptionInfoFilter())

    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Enrich the record with exception info if an exception is active.

        Args:
            record: The log record to enrich.

        Returns:
            Always ``True``; this filter never suppresses records.

        """
        if record.exc_info is None:
            exc_info = sys.exc_info()
            if exc_info[0] is not None:
                record.exc_info = exc_info
        return True


class PlynthHTTPFilter(ThrottleLogs):
    """Flood-protection filter pre-configured for the ``plynth.http`` logger.

    A convenience subclass of ``ThrottleLogs`` that targets the
    ``plynth.http`` logger namespace. Operators can attach it to any handler
    with zero extra configuration to prevent log flooding when an upstream
    becomes unavailable.

    Args:
        limit: Maximum records allowed per window. Defaults to ``60``.
        window: Window duration in seconds. Defaults to ``3600`` (one hour).

    Example::

        import logging
        from plynth.log import PlynthHTTPFilter

        handler = logging.StreamHandler()
        handler.addFilter(PlynthHTTPFilter())

    Equivalent to::

        handler.addFilter(ThrottleLogs(name="plynth.http", limit=60))

    """

    def __init__(self, *, limit: int = 60, window: int = 3600) -> None:
        """Initialize PlynthHTTPFilter."""
        super().__init__(name="plynth.http", limit=limit, window=window)
