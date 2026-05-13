"""Reusable Python logging utilities for Plynth services.

This package provides standalone ``logging`` framework utilities — filters
and a formatter — that can be attached to any Python log handler.
They are independent of the Plynth transport and middleware layer and do not
require Plynth's request/response model.

Available components:

- ``ThrottleLogs`` — suppresses repeated log records after a configurable
  per-window limit, preventing log- and Sentry-flooding from noisy upstreams.
- ``ExceptionInfoFilter`` — injects active exception context into records
  that were emitted without it.
- ``PlynthHTTPFilter`` — convenience subclass of ``ThrottleLogs``
  pre-configured for the ``plynth.http`` logger with sensible defaults.
- ``StructuredFormatter`` — renders log records as single-line JSON objects
  suitable for log-aggregation pipelines (ELK, Cloud Logging, Datadog).

Usage example::

    import logging
    from plynth.log import PlynthHTTPFilter, StructuredFormatter
    from plynth.middleware.logging import LoggingMiddleware
    from plynth.http.transport import HttpxSyncTransport

    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    handler.addFilter(PlynthHTTPFilter())
    logging.getLogger("plynth").addHandler(handler)
    logging.getLogger("plynth").setLevel(logging.INFO)

    transport = HttpxSyncTransport(middlewares=[LoggingMiddleware()])
"""

from __future__ import annotations

from plynth.log.filters import ExceptionInfoFilter, PlynthHTTPFilter, ThrottleLogs
from plynth.log.formatter import StructuredFormatter

__all__ = [
    "ExceptionInfoFilter",
    "PlynthHTTPFilter",
    "StructuredFormatter",
    "ThrottleLogs",
]
