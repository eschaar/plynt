"""Tests for plynth.log.StructuredFormatter."""

from __future__ import annotations

import json
import logging
import sys

from plynth.log import StructuredFormatter


class TestStructuredFormatter:
    """Test suite for StructuredFormatter."""

    def _make_record(self, msg: str = "hello") -> logging.LogRecord:
        """Handle make record."""
        return logging.LogRecord(
            name="plynth.http",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def test_format_returns_valid_json(self) -> None:
        """Validate format returns valid json."""
        formatter = StructuredFormatter()
        output = formatter.format(self._make_record())
        parsed = json.loads(output)
        assert parsed["message"] == "hello"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "plynth.http"
        assert "time" in parsed

    def test_format_omits_exc_info_when_none(self) -> None:
        """Validate format omits exc info when none."""
        formatter = StructuredFormatter()
        parsed = json.loads(formatter.format(self._make_record()))
        assert "exc_info" not in parsed

    def test_format_includes_exc_info_when_present(self) -> None:
        """Validate format includes exc info when present."""
        formatter = StructuredFormatter()
        record = self._make_record()
        try:
            raise ValueError("test error")
        except ValueError:
            record.exc_info = sys.exc_info()
        parsed = json.loads(formatter.format(record))
        assert "exc_info" in parsed
        assert "ValueError" in parsed["exc_info"]
        assert "test error" in parsed["exc_info"]

    def test_extra_fields_are_included_in_json(self) -> None:
        """Validate extra fields are included in json."""
        logger = logging.getLogger("plynth.test.extra")
        records: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            """Represent Capture."""

            def emit(self, record: logging.LogRecord) -> None:
                """Return emit."""
                records.append(record)

        handler = _Capture()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            logger.debug(
                "test message",
                extra={
                    "http.request.method": "GET",
                    "http.response.status_code": 200,
                    "url.full": "https://example.com/api",
                    "event.duration": 42_000_000,
                },
            )
        finally:
            logger.removeHandler(handler)

        assert len(records) == 1
        parsed = json.loads(StructuredFormatter().format(records[0]))
        assert parsed["http.request.method"] == "GET"
        assert parsed["http.response.status_code"] == 200
        assert parsed["url.full"] == "https://example.com/api"
        assert parsed["event.duration"] == 42_000_000

    def test_standard_fields_not_duplicated_as_extra(self) -> None:
        """Validate standard fields not duplicated as extra."""
        formatter = StructuredFormatter()
        parsed = json.loads(formatter.format(self._make_record()))
        # Standard LogRecord attributes must not bleed into the output as
        # top-level extra keys.
        assert "lineno" not in parsed
        assert "pathname" not in parsed
        assert "levelno" not in parsed
