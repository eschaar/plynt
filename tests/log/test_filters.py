"""Tests for plynt.log filters (ThrottleLogs, ExceptionInfoFilter,
PlyntHTTPFilter)."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

import pytest

from plynt.base import RequestIDPolicy, get_request_id
from plynt.log import (
    ExceptionInfoFilter,
    PlyntHTTPFilter,
    RequestIDFilter,
    StructuredFormatter,
    ThrottleLogs,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    name: str = "test.logger",
    msg: str = "test message",
    created: float | None = None,
) -> logging.LogRecord:
    """Create a ``LogRecord`` with an optional fixed ``created`` timestamp.

    Setting ``created`` to a known float lets tests manipulate the apparent
    time of the record, which is needed to exercise window-reset behaviour
    without real clock sleeps.
    """
    record = logging.LogRecord(
        name=name,
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    if created is not None:
        record.created = created
    return record


class TestRequestIDFilter:
    def test_active_scope_adds_request_id_without_suppressing_record(self) -> None:
        record = _make_record()
        with RequestIDPolicy().scope("request-123"):
            assert RequestIDFilter().filter(record) is True
        assert record.__dict__["request_id"] == "request-123"

    def test_missing_scope_adds_placeholder_without_generating_id(self) -> None:
        record = _make_record()
        assert RequestIDFilter().filter(record) is True
        assert record.__dict__["request_id"] == "-"
        assert get_request_id() is None

    def test_current_context_replaces_existing_request_id(self) -> None:
        record = _make_record()
        record.request_id = "stale"
        with RequestIDPolicy().scope("current"):
            RequestIDFilter().filter(record)
        assert record.__dict__["request_id"] == "current"
        RequestIDFilter().filter(record)
        assert record.__dict__["request_id"] == "-"

    def test_exception_exit_restores_outer_id_for_logging(self) -> None:
        policy = RequestIDPolicy()
        log_filter = RequestIDFilter()
        record = _make_record()
        with policy.scope("outer"):
            with pytest.raises(ValueError, match="failure"):
                with policy.scope("inner"):
                    log_filter.filter(record)
                    assert record.__dict__["request_id"] == "inner"
                    raise ValueError("failure")
            log_filter.filter(record)
            assert record.__dict__["request_id"] == "outer"
        log_filter.filter(record)
        assert record.__dict__["request_id"] == "-"

    @pytest.mark.parametrize("structured", [False, True])
    def test_handler_enriches_child_logger_records(self, structured: bool) -> None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(RequestIDFilter())
        handler.setFormatter(
            StructuredFormatter()
            if structured
            else logging.Formatter("%(request_id)s %(message)s")
        )
        parent = logging.Logger("application")
        parent.addHandler(handler)
        child = logging.Logger("application.child")
        child.parent = parent
        with RequestIDPolicy().scope("handler-id"):
            child.warning("scoped")
        child.warning("outside")
        lines = stream.getvalue().splitlines()
        if structured:
            assert json.loads(lines[0])["request_id"] == "handler-id"
            assert json.loads(lines[1])["request_id"] == "-"
        else:
            assert lines == ["handler-id scoped", "- outside"]

    @pytest.mark.asyncio
    async def test_shared_filter_keeps_concurrent_task_ids_isolated(self) -> None:
        policy = RequestIDPolicy()
        log_filter = RequestIDFilter()

        async def log_in_scope(request_id: str) -> str:
            with policy.scope(request_id):
                await asyncio.sleep(0)
                record = _make_record()
                log_filter.filter(record)
                return str(record.__dict__["request_id"])

        first, second = await asyncio.gather(
            log_in_scope("first"), log_in_scope("second")
        )
        assert first == "first"
        assert second == "second"
        assert get_request_id() is None

    def test_worker_logging_uses_explicitly_copied_context(self) -> None:
        log_filter = RequestIDFilter()

        def log_request_id() -> str:
            record = _make_record()
            log_filter.filter(record)
            return str(record.__dict__["request_id"])

        with ThreadPoolExecutor(max_workers=1) as executor:
            with RequestIDPolicy().scope("copied"):
                assert executor.submit(log_request_id).result() == "-"
                context = copy_context()
                assert executor.submit(context.run, log_request_id).result() == "copied"
            assert executor.submit(log_request_id).result() == "-"


# ---------------------------------------------------------------------------
# ThrottleLogs
# ---------------------------------------------------------------------------


class TestThrottleLogs:
    """Test suite for ThrottleLogs."""

    def test_allows_records_within_limit(self) -> None:
        """Validate allows records within limit."""
        f = ThrottleLogs(limit=3, window=3600)
        for _ in range(3):
            assert f.filter(_make_record(created=1000.0)) is True

    def test_suppresses_records_beyond_limit(self) -> None:
        """Validate suppresses records beyond limit."""
        f = ThrottleLogs(limit=2, window=3600)
        f.filter(_make_record(created=1000.0))
        f.filter(_make_record(created=1000.0))
        assert f.filter(_make_record(created=1000.0)) is False

    def test_limit_zero_suppresses_from_first_record(self) -> None:
        """Validate limit zero suppresses from first record."""
        f = ThrottleLogs(limit=0, window=3600)
        assert f.filter(_make_record(created=1000.0)) is False

    def test_window_reset_allows_records_again(self) -> None:
        """Validate window reset allows records again."""
        f = ThrottleLogs(limit=1, window=3600)
        assert f.filter(_make_record(created=1000.0)) is True
        # same window — should be suppressed
        assert f.filter(_make_record(created=1000.0)) is False
        # past the window boundary — counter resets
        assert f.filter(_make_record(created=5001.0)) is True

    def test_window_boundary_is_inclusive(self) -> None:
        """A record arriving exactly at the window boundary starts a new window."""
        f = ThrottleLogs(limit=1, window=3600)
        f.filter(_make_record(created=1000.0))  # window_start = 1000.0
        # created - window_start == window => new window
        assert f.filter(_make_record(created=4600.0)) is True

    def test_name_filter_passes_unrelated_loggers_unconditionally(self) -> None:
        """Validate name filter passes unrelated loggers unconditionally."""
        f = ThrottleLogs(name="plynt.http", limit=0, window=3600)
        # Even with limit=0, unrelated loggers are never suppressed.
        for _ in range(10):
            assert f.filter(_make_record(name="django.request")) is True

    def test_name_filter_targets_exact_prefix(self) -> None:
        """Validate name filter targets exact prefix."""
        f = ThrottleLogs(name="plynt.http", limit=1, window=3600)
        # First record from matched logger passes.
        assert f.filter(_make_record(name="plynt.http", created=1000.0)) is True
        # Second record from matched logger is suppressed.
        assert f.filter(_make_record(name="plynt.http", created=1000.0)) is False

    def test_name_filter_matches_child_loggers(self) -> None:
        """Logger names that are children of the target prefix are also targeted."""
        f = ThrottleLogs(name="plynt.http", limit=1, window=3600)
        f.filter(_make_record(name="plynt.http.transport", created=1000.0))
        assert f.filter(_make_record(name="plynt.http.auth", created=1000.0)) is False

    def test_no_name_filter_counts_all_loggers(self) -> None:
        """Validate no name filter counts all loggers."""
        f = ThrottleLogs(limit=2, window=3600)
        f.filter(_make_record(name="logger.a", created=1000.0))
        f.filter(_make_record(name="logger.b", created=1000.0))
        assert f.filter(_make_record(name="logger.c", created=1000.0)) is False

    def test_pattern_filter_passes_non_matching_messages(self) -> None:
        """Validate pattern filter passes non matching messages."""
        pattern = re.compile(r"connection refused")
        f = ThrottleLogs(limit=0, pattern=pattern, window=3600)
        # Non-matching messages pass through regardless of limit.
        assert f.filter(_make_record(msg="all good", created=1000.0)) is True

    def test_pattern_filter_counts_matching_messages(self) -> None:
        """Validate pattern filter counts matching messages."""
        pattern = re.compile(r"timeout")
        f = ThrottleLogs(limit=1, pattern=pattern, window=3600)
        assert f.filter(_make_record(msg="upstream timeout", created=1000.0)) is True
        assert f.filter(_make_record(msg="upstream timeout", created=1000.0)) is False

    def test_pattern_and_name_both_required_to_count(self) -> None:
        """A record must match both name AND pattern to be counted."""
        pattern = re.compile(r"timeout")
        f = ThrottleLogs(name="plynt.http", limit=0, pattern=pattern, window=3600)
        # Wrong logger — passes even though pattern matches.
        assert f.filter(_make_record(name="other", msg="timeout")) is True
        # Right logger but wrong message — also passes.
        assert f.filter(_make_record(name="plynt.http", msg="all good")) is True

    def test_default_limit_is_sixty(self) -> None:
        """Validate default limit is sixty."""
        f = ThrottleLogs()
        assert f._limit == 60

    def test_default_window_is_one_hour(self) -> None:
        """Validate default window is one hour."""
        f = ThrottleLogs()
        assert f._window == 3600


# ---------------------------------------------------------------------------
# ExceptionInfoFilter
# ---------------------------------------------------------------------------


class TestExceptionInfoFilter:
    """Test suite for ExceptionInfoFilter."""

    def test_always_returns_true(self) -> None:
        """Validate always returns true."""
        f = ExceptionInfoFilter()
        assert f.filter(_make_record()) is True

    def test_returns_true_even_when_no_exception_active(self) -> None:
        """Validate returns true even when no exception active."""
        f = ExceptionInfoFilter()
        record = _make_record()
        result = f.filter(record)
        assert result is True
        assert record.exc_info is None

    def test_injects_exc_info_when_exception_is_active(self) -> None:
        """Validate injects exc info when exception is active."""
        f = ExceptionInfoFilter()
        record = _make_record()
        try:
            raise ValueError("boom")
        except ValueError:
            f.filter(record)

        assert record.exc_info is not None
        exc_type, exc_val, _tb = record.exc_info
        assert exc_type is ValueError
        assert str(exc_val) == "boom"

    def test_does_not_overwrite_existing_exc_info(self) -> None:
        """Validate does not overwrite existing exc info."""
        f = ExceptionInfoFilter()
        sentinel: tuple[type[BaseException], BaseException, None] = (
            RuntimeError,
            RuntimeError("original"),
            None,
        )
        record = _make_record()
        record.exc_info = sentinel
        try:
            raise ValueError("other")
        except ValueError:
            f.filter(record)

        # Original exc_info must be preserved.
        assert record.exc_info is sentinel

    def test_no_exc_info_injected_outside_except_block(self) -> None:
        """Outside an active handler, sys.exc_info() returns (None, None, None)."""
        f = ExceptionInfoFilter()
        record = _make_record()
        # Ensure no exception is active by calling explicitly outside any handler.
        f.filter(record)
        assert record.exc_info is None

    def test_exc_type_is_attached_correctly(self) -> None:
        """Validate exc type is attached correctly."""
        f = ExceptionInfoFilter()
        record = _make_record()
        try:
            raise TypeError("type error")
        except TypeError:
            f.filter(record)

        assert record.exc_info is not None
        assert record.exc_info[0] is TypeError

    @pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO, logging.ERROR])
    def test_works_at_all_log_levels(self, level: int) -> None:
        """Validate works at all log levels."""
        f = ExceptionInfoFilter()
        record = logging.LogRecord(
            name="test",
            level=level,
            pathname="",
            lineno=0,
            msg="msg",
            args=(),
            exc_info=None,
        )
        assert f.filter(record) is True


# ---------------------------------------------------------------------------
# PlyntHTTPFilter
# ---------------------------------------------------------------------------


class TestPlyntHTTPFilter:
    """Test suite for PlyntHTTPFilter."""

    def test_default_parameters_target_plynt_http_namespace(self) -> None:
        """Validate default parameters target plynt http namespace."""
        f = PlyntHTTPFilter()
        assert f._limit == 60
        assert f._window == 3600

    def test_custom_limit_and_window_are_forwarded(self) -> None:
        """Validate custom limit and window are forwarded."""
        f = PlyntHTTPFilter(limit=5, window=300)
        assert f._limit == 5
        assert f._window == 300
