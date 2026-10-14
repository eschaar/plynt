"""Reusable Python logging utilities for Plynt services.

This package provides standalone ``logging`` framework utilities — filters
and a formatter — that can be attached to any Python log handler.
They are independent of the Plynt transport and middleware layer and do not
require Plynt's request/response model.

Available components:

- ``ThrottleLogs`` — suppresses repeated log records after a configurable
  per-window limit, preventing log- and Sentry-flooding from noisy upstreams.
- ``ExceptionInfoFilter`` — injects active exception context into records
  that were emitted without it.
- ``PlyntHTTPFilter`` — convenience subclass of ``ThrottleLogs``
  pre-configured for the ``plynt.http`` logger with sensible defaults.
- ``StructuredFormatter`` — renders log records as single-line JSON objects
  suitable for log-aggregation pipelines (ELK, Cloud Logging, Datadog).

Usage example::

    import logging
    from plynt.log import PlyntHTTPFilter, StructuredFormatter
    from plynt.middleware.logging import LoggingMiddleware
    from plynt.http.transport import HttpxSyncTransport

    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    handler.addFilter(PlyntHTTPFilter())
    logging.getLogger("plynt").addHandler(handler)
    logging.getLogger("plynt").setLevel(logging.INFO)

    transport = HttpxSyncTransport(middlewares=[LoggingMiddleware()])
"""

from __future__ import annotations

from plynt.log.filters import ExceptionInfoFilter, PlyntHTTPFilter, ThrottleLogs
from plynt.log.formatter import StructuredFormatter

__all__ = [
    "ExceptionInfoFilter",
    "PlyntHTTPFilter",
    "StructuredFormatter",
    "ThrottleLogs",
]
