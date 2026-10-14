"""Tests for plynt.middleware.logging (LoggingMiddleware, AsyncLoggingMiddleware)."""

from __future__ import annotations

import logging

import pytest

from plynt.base.middleware import AsyncMiddleware, SyncMiddleware
from plynt.base.request import Request
from plynt.base.response import AsyncStreamingResponse, Response, StreamingResponse
from plynt.middleware.logging import AsyncLoggingMiddleware, LoggingMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUEST = Request(method="GET", url="https://example.com/api/v1/resource")
_RESPONSE = Response(status_code=200, content=b"ok")


def _noop(_request: Request) -> Response:  # pylint: disable=unused-argument
    """Handle noop."""
    return _RESPONSE


async def _async_noop(
    _request: Request,
) -> Response:  # pylint: disable=unused-argument
    """Handle async noop."""
    return _RESPONSE


# ---------------------------------------------------------------------------
# TestLoggingMiddleware
# ---------------------------------------------------------------------------


class TestLoggingMiddleware:
    """Verify LoggingMiddleware satisfies SyncMiddleware and logs correctly."""

    def test_satisfies_sync_middleware_protocol(self) -> None:
        """Validate satisfies sync middleware protocol."""
        assert isinstance(LoggingMiddleware(), SyncMiddleware)

    def test_handle_calls_next_handler(self) -> None:
        """Validate handle calls next handler."""
        called: list[Request] = []

        def next_handler(req: Request) -> Response:
            """Return next handler."""
            called.append(req)
            return _RESPONSE

        mw = LoggingMiddleware()
        result = mw.handle(_REQUEST, next_handler)
        assert len(called) == 1
        assert result is _RESPONSE

    def test_handle_returns_response_from_next(self) -> None:
        """Validate handle returns response from next."""
        expected = Response(status_code=201, content=b"created")
        mw = LoggingMiddleware()
        result = mw.handle(_REQUEST, lambda r: expected)
        assert result is expected

    def test_logs_request_at_info_level(self, caplog: pytest.LogCaptureFixture) -> None:
        """Validate logs request at info level."""
        with caplog.at_level(logging.INFO, logger="plynt.http"):
            LoggingMiddleware().handle(_REQUEST, _noop)

        request_records = [r for r in caplog.records if "-->" in r.message]
        assert len(request_records) == 1
        assert _REQUEST.method in request_records[0].message
        assert str(_REQUEST.url) in request_records[0].message

    def test_logs_response_at_info_level(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate logs response at info level."""
        with caplog.at_level(logging.INFO, logger="plynt.http"):
            LoggingMiddleware().handle(_REQUEST, _noop)

        response_records = [r for r in caplog.records if "<--" in r.message]
        assert len(response_records) == 1
        assert str(_RESPONSE.status_code) in response_records[0].message

    def test_response_log_includes_elapsed_time(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate response log includes elapsed time."""
        with caplog.at_level(logging.INFO, logger="plynt.http"):
            LoggingMiddleware().handle(_REQUEST, _noop)

        response_message = next(r.message for r in caplog.records if "<--" in r.message)
        assert "ms" in response_message

    def test_request_record_has_ecs_extra_fields(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate request record has ecs extra fields."""
        with caplog.at_level(logging.INFO, logger="plynt.http"):
            LoggingMiddleware().handle(_REQUEST, _noop)

        rec = next(r for r in caplog.records if "-->" in r.message)
        assert getattr(rec, "event.action") == "http-request"
        assert getattr(rec, "http.request.method") == _REQUEST.method
        assert getattr(rec, "url.full") == str(_REQUEST.url)

    def test_sensitive_query_values_are_redacted(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate sensitive query values are redacted in request/response logs."""
        request = Request(
            method="GET",
            url="https://example.com/api?q=ok&access_token=secret",
        )

        with caplog.at_level(logging.INFO, logger="plynt.http"):
            LoggingMiddleware().handle(request, _noop)

        request_record = next(r for r in caplog.records if "-->" in r.message)
        response_record = next(r for r in caplog.records if "<--" in r.message)

        assert "access_token=%5BREDACTED%5D" in request_record.message
        assert "access_token=%5BREDACTED%5D" in response_record.message
        assert "access_token=secret" not in request_record.message
        assert "access_token=secret" not in response_record.message

    def test_response_record_has_ecs_extra_fields(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate response record has ecs extra fields."""
        with caplog.at_level(logging.INFO, logger="plynt.http"):
            LoggingMiddleware().handle(_REQUEST, _noop)

        rec = next(r for r in caplog.records if "<--" in r.message)
        assert getattr(rec, "event.action") == "http-response"
        assert getattr(rec, "http.request.method") == _REQUEST.method
        assert getattr(rec, "http.response.status_code") == _RESPONSE.status_code
        assert getattr(rec, "http.response.streaming") is False
        assert getattr(rec, "url.full") == str(_REQUEST.url)
        assert isinstance(getattr(rec, "event.duration"), int)

    def test_custom_logger_is_used(self) -> None:
        """Validate custom logger is used."""
        custom_logger = logging.getLogger("test.custom")
        records: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            """Represent Capture."""

            def emit(self, record: logging.LogRecord) -> None:
                """Return emit."""
                records.append(record)

        handler = _Capture()
        custom_logger.addHandler(handler)
        custom_logger.setLevel(logging.DEBUG)
        try:
            LoggingMiddleware(logger=custom_logger).handle(_REQUEST, _noop)
        finally:
            custom_logger.removeHandler(handler)

        assert len(records) == 2

    def test_custom_level_is_used(self, caplog: pytest.LogCaptureFixture) -> None:
        """Validate custom level is used."""
        with caplog.at_level(logging.DEBUG, logger="plynt.http"):
            LoggingMiddleware(level=logging.DEBUG).handle(_REQUEST, _noop)

        assert all(r.levelno == logging.DEBUG for r in caplog.records)

    def test_request_logged_before_response(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate request logged before response."""
        with caplog.at_level(logging.INFO, logger="plynt.http"):
            LoggingMiddleware().handle(_REQUEST, _noop)

        messages = [r.message for r in caplog.records]
        req_idx = next(i for i, m in enumerate(messages) if "-->" in m)
        res_idx = next(i for i, m in enumerate(messages) if "<--" in m)
        assert req_idx < res_idx

    def test_streaming_response_log_contains_streaming_marker(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate streaming responses are explicitly marked in logs."""
        streaming_response = StreamingResponse(status_code=200, _raw=object())

        with caplog.at_level(logging.INFO, logger="plynt.http"):
            LoggingMiddleware().handle(_REQUEST, lambda _r: streaming_response)

        response_record = next(r for r in caplog.records if "<--" in r.message)
        assert "(streaming, no body)" in response_record.message
        assert getattr(response_record, "http.response.streaming", False) is True


# ---------------------------------------------------------------------------
# TestAsyncLoggingMiddleware
# ---------------------------------------------------------------------------


class TestAsyncLoggingMiddleware:
    """Verify AsyncLoggingMiddleware satisfies AsyncMiddleware and logs correctly."""

    def test_satisfies_async_middleware_protocol(self) -> None:
        """Validate satisfies async middleware protocol."""
        assert isinstance(AsyncLoggingMiddleware(), AsyncMiddleware)

    @pytest.mark.anyio
    async def test_handle_calls_next_handler(self) -> None:
        """Validate handle calls next handler."""
        called: list[Request] = []

        async def next_handler(req: Request) -> Response:
            """Return next handler."""
            called.append(req)
            return _RESPONSE

        mw = AsyncLoggingMiddleware()
        result = await mw.handle(_REQUEST, next_handler)
        assert len(called) == 1
        assert result is _RESPONSE

    @pytest.mark.anyio
    async def test_handle_returns_response_from_next(self) -> None:
        """Validate handle returns response from next."""
        expected = Response(status_code=202, content=b"accepted")

        async def _return_expected(
            _req: Request,
        ) -> Response:  # pylint: disable=unused-argument
            """Handle return expected."""
            return expected

        mw = AsyncLoggingMiddleware()
        result = await mw.handle(_REQUEST, _return_expected)
        assert result is expected

    @pytest.mark.anyio
    async def test_logs_request_and_response(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate logs request and response."""
        with caplog.at_level(logging.INFO, logger="plynt.http"):
            await AsyncLoggingMiddleware().handle(_REQUEST, _async_noop)

        assert any("-->" in r.message for r in caplog.records)
        assert any("<--" in r.message for r in caplog.records)

    @pytest.mark.anyio
    async def test_response_log_includes_elapsed_time(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate response log includes elapsed time."""
        with caplog.at_level(logging.INFO, logger="plynt.http"):
            await AsyncLoggingMiddleware().handle(_REQUEST, _async_noop)

        response_message = next(r.message for r in caplog.records if "<--" in r.message)
        assert "ms" in response_message

    @pytest.mark.anyio
    async def test_sensitive_query_values_are_redacted(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate sensitive query values are redacted in async logs."""
        request = Request(
            method="GET",
            url="https://example.com/api?q=ok&token=secret",
        )

        with caplog.at_level(logging.INFO, logger="plynt.http"):
            await AsyncLoggingMiddleware().handle(request, _async_noop)

        request_record = next(r for r in caplog.records if "-->" in r.message)
        response_record = next(r for r in caplog.records if "<--" in r.message)

        assert "token=%5BREDACTED%5D" in request_record.message
        assert "token=%5BREDACTED%5D" in response_record.message
        assert "token=secret" not in request_record.message
        assert "token=secret" not in response_record.message

    @pytest.mark.anyio
    async def test_custom_logger_is_used(self) -> None:
        """Validate custom logger is used."""
        custom_logger = logging.getLogger("test.async.custom")
        records: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            """Represent Capture."""

            def emit(self, record: logging.LogRecord) -> None:
                """Return emit."""
                records.append(record)

        handler = _Capture()
        custom_logger.addHandler(handler)
        custom_logger.setLevel(logging.DEBUG)
        try:
            await AsyncLoggingMiddleware(logger=custom_logger).handle(
                _REQUEST, _async_noop
            )
        finally:
            custom_logger.removeHandler(handler)

        assert len(records) == 2

    @pytest.mark.anyio
    async def test_streaming_response_log_contains_streaming_marker(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validate async streaming responses are explicitly marked in logs."""
        streaming_response = AsyncStreamingResponse(status_code=200, _raw=object())

        async def _return_streaming(_req: Request) -> Response:
            """Return streaming response for async middleware test."""
            return streaming_response

        with caplog.at_level(logging.INFO, logger="plynt.http"):
            await AsyncLoggingMiddleware().handle(_REQUEST, _return_streaming)

        response_record = next(r for r in caplog.records if "<--" in r.message)
        assert "(streaming, no body)" in response_record.message
        assert getattr(response_record, "http.response.streaming", False) is True
