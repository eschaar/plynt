"""Log formatter for Plynth services.

Provides ``StructuredFormatter``, a ``logging.Formatter`` subclass that
renders records as single-line JSON objects suitable for log-aggregation
pipelines.
"""

from __future__ import annotations

import datetime
import json
import logging

__all__ = ["StructuredFormatter"]

# Standard attributes present on every LogRecord.  Any key on the record's
# __dict__ that is NOT in this set was injected via extra={} and will be
# included in the JSON output as a structured field.
_STANDARD_LOG_RECORD_ATTRS: frozenset[str] = frozenset(
    {
        "args",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class StructuredFormatter(logging.Formatter):
    """Format log records as single-line JSON objects.

    Renders each record as a JSON object with the following fixed fields:

    - ``time``: ISO 8601 timestamp in UTC (e.g. ``"2026-03-14T12:00:00.000Z"``).
    - ``level``: Log level name (e.g. ``"DEBUG"``, ``"WARNING"``).
    - ``logger``: Logger name (e.g. ``"plynth.http.transport"``).
    - ``message``: Formatted log message.
    - ``exc_info``: Formatted exception string, omitted when no exception
      is attached to the record.

    Any extra fields passed via ``extra={}`` on the logging call are
    serialised after the fixed fields using their original key names.
    Plynth uses `Elastic Common Schema (ECS)
    <https://www.elastic.co/guide/en/ecs/current/index.html>`_ field names
    for HTTP events (``http.request.method``, ``http.response.status_code``,
    ``url.full``, ``event.duration``, ``event.action``).

    Credentials and request/response bodies are never included — this
    formatter only serialises the fields set by the logging system itself.

    Suitable for use with log-aggregation pipelines (ELK, Cloud Logging,
    Datadog, etc.) that expect one JSON object per line.

    Example — direct use::

        import logging
        from plynth.log import StructuredFormatter

        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        logging.getLogger("plynth").addHandler(handler)

    Example — Django ``LOGGING`` dict::

        LOGGING = {
            "version": 1,
            "formatters": {
                "json": {"()": "plynth.log.StructuredFormatter"},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                },
            },
            "loggers": {
                "plynth": {
                    "handlers": ["console"],
                    "level": "DEBUG",
                    "propagate": False,
                },
            },
        }

    """

    def format(self, record: logging.LogRecord) -> str:
        """Render *record* as a single-line JSON string.

        Args:
            record: The log record to format.

        Returns:
            A single-line JSON string with ``time``, ``level``, ``logger``,
            ``message``, any ``extra`` fields, and optionally ``exc_info``.

        """
        ts = datetime.datetime.fromtimestamp(record.created, tz=datetime.UTC)
        payload: dict[str, object] = {
            "time": (
                ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Append any structured extra fields (e.g. ECS HTTP fields).
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
