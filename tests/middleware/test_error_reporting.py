"""Verify reporting preserves failures and isolates truthful retry observations"""

import asyncio
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from plynt.base import (
    InvalidInputError,
    Request,
    Response,
    RetryPolicy,
    default_error_envelope,
    get_error_event_id,
)
from plynt.base.reporting_context import (
    get_retry_attempts,
    observe_retry_attempt,
    reporting_scope,
)
from plynt.http.errors import NotFoundError
from plynt.middleware import AsyncErrorReportingMiddleware, ErrorReportingMiddleware
from plynt.middleware.retry import AsyncRetryMiddleware, RetryMiddleware


class _Reporter:
    def __init__(self, fail: bool = False, event_id: str | None = "event") -> None:
        self.calls: list[tuple[Exception, Mapping[str, object]]] = []
        self.fail = fail
        self.event_id = event_id

    def report(self, exc: Exception, context: Mapping[str, object]) -> str | None:
        if self.fail:
            raise ValueError("private-reporter")
        self.calls.append((exc, context))
        return self.event_id

    async def areport(
        self, exc: Exception, context: Mapping[str, object]
    ) -> str | None:
        return self.report(exc, context)


class TestErrorReportingMiddleware:
    def test_malformed_url_is_omitted_without_losing_error_report(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        reporter = _Reporter()
        error = ValueError("private-original")

        def failing(request: Request) -> Response:
            raise error

        with pytest.raises(ValueError) as caught:
            ErrorReportingMiddleware(reporter).handle(
                Request("GET", "https://[::1?token=private-url"), failing
            )
        assert caught.value is error
        assert reporter.calls == [(error, {"method": "GET"})]
        assert get_error_event_id(error) == "event"
        assert len(caplog.records) == 1
        assert caplog.records[0].exc_info is None
        assert "private" not in caplog.text

    @pytest.mark.parametrize("status", [200, 503])
    def test_success_and_returned_error_status_are_not_reported(
        self, status: int
    ) -> None:
        reporter = _Reporter()
        middleware = ErrorReportingMiddleware(reporter)
        response = Response(status_code=status)
        assert middleware.handle(Request("GET", "/"), lambda _: response) is response
        assert reporter.calls == []

    def test_context_redacts_credentials_and_omits_body_and_arbitrary_details(
        self,
    ) -> None:
        reporter = _Reporter()
        middleware = ErrorReportingMiddleware(
            reporter, context_provider=lambda _: {"service": "items"}
        )
        error = NotFoundError(details={"password": "private"})
        error.attach_response(
            Response(status_code=404, headers={"X-Request-ID": "upstream"})
        )

        def failing(request: Request) -> Response:
            raise error

        request = Request(
            "GET",
            "https://user:private@example.test/items?token=private&q=ok#private",
            headers={"Authorization": "private"},
            content=b"private",
        )
        with pytest.raises(NotFoundError) as caught:
            middleware.handle(request, failing)
        assert caught.value is error
        assert get_error_event_id(error) == "event"
        received, context = reporter.calls[0]
        assert received is error
        assert context == {
            "method": "GET",
            "url": "https://example.test/items?token=%5BREDACTED%5D&q=ok",
            "service": "items",
            "upstream_status": 404,
            "upstream_request_id": "upstream",
        }
        assert "private" not in str(context)

    @pytest.mark.parametrize("header", ["bad id", "a" * 129])
    def test_invalid_upstream_id_is_omitted(self, header: str) -> None:
        reporter = _Reporter()
        error = NotFoundError()
        error.attach_response(
            Response(status_code=404, headers={"X-Request-ID": header})
        )

        def failing(request: Request) -> Response:
            raise error

        with pytest.raises(NotFoundError):
            ErrorReportingMiddleware(reporter).handle(Request("GET", "/"), failing)
        assert "upstream_request_id" not in reporter.calls[0][1]

    @pytest.mark.parametrize(
        "provided", [{"unknown": "value"}, {"service": ""}, {"service": "bad\nvalue"}]
    )
    def test_invalid_provider_preserves_original_and_logs_safely(
        self, provided: dict[str, str], caplog: pytest.LogCaptureFixture
    ) -> None:
        reporter = _Reporter()
        error = RuntimeError("private-original")

        def failing(request: Request) -> Response:
            raise error

        with pytest.raises(RuntimeError) as caught:
            ErrorReportingMiddleware(
                reporter, context_provider=lambda _: provided
            ).handle(Request("GET", "/"), failing)
        assert caught.value is error
        assert reporter.calls == []
        assert len(caplog.records) == 1
        assert "private" not in caplog.text
        assert caplog.records[0].exc_info is None

    @pytest.mark.parametrize("attempts", [1, 3])
    def test_retry_counts_are_observed_and_reported_once(self, attempts: int) -> None:
        reporter = _Reporter()
        retry = RetryMiddleware(
            RetryPolicy(
                max_attempts=attempts,
                backoff_initial=0,
                retryable_exception_classifier=lambda _: True,
            )
        )
        error = ConnectionError("failure")

        def failing(request: Request) -> Response:
            raise error

        with pytest.raises(ConnectionError) as caught:
            ErrorReportingMiddleware(reporter).handle(
                Request("GET", "/"),
                lambda request: retry.handle(request, failing),
            )
        assert caught.value is error
        assert len(reporter.calls) == 1
        assert reporter.calls[0][1]["attempts"] == attempts
        assert reporter.calls[0][1]["retries"] == attempts - 1
        assert get_retry_attempts() is None

    def test_reporter_failure_does_not_replace_original(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        def failing(request: Request) -> Response:
            raise RuntimeError("original")

        with pytest.raises(RuntimeError, match="original"):
            ErrorReportingMiddleware(_Reporter(fail=True)).handle(
                Request("GET", "/"), failing
            )
        assert len(caplog.records) == 1
        assert "private-reporter" not in caplog.text


class TestAsyncErrorReportingMiddleware:
    @pytest.mark.asyncio
    async def test_malformed_url_still_reports_original_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        reporter = _Reporter()
        error = ValueError("private-original")

        async def failing(request: Request) -> Response:
            raise error

        with pytest.raises(ValueError) as caught:
            await AsyncErrorReportingMiddleware(reporter).handle(
                Request("GET", "https://[::1?token=private-url"), failing
            )
        assert caught.value is error
        assert reporter.calls == [(error, {"method": "GET"})]
        assert get_error_event_id(error) == "event"
        assert len(caplog.records) == 1
        assert "private" not in caplog.text

    @pytest.mark.asyncio
    async def test_concurrent_retries_keep_counts_separate(self) -> None:
        reporter = _Reporter()
        middleware = AsyncErrorReportingMiddleware(reporter)

        async def run(attempts: int) -> None:
            retry = AsyncRetryMiddleware(
                RetryPolicy(
                    max_attempts=attempts,
                    backoff_initial=0,
                    retryable_exception_classifier=lambda _: True,
                )
            )

            async def failing(request: Request) -> Response:
                await asyncio.sleep(0)
                raise ConnectionError(str(attempts))

            with pytest.raises(ConnectionError):
                await middleware.handle(
                    Request("GET", "/"),
                    lambda request: retry.handle(request, failing),
                )
            assert get_retry_attempts() is None

        await asyncio.gather(run(1), run(3))
        assert {context["attempts"] for _, context in reporter.calls} == {1, 3}

    @pytest.mark.asyncio
    async def test_success_passes_through(self) -> None:
        reporter = _Reporter()
        response = Response(status_code=200)

        async def handler(request: Request) -> Response:
            return response

        assert (
            await AsyncErrorReportingMiddleware(reporter).handle(
                Request("GET", "/"), handler
            )
            is response
        )
        assert reporter.calls == []

    @pytest.mark.asyncio
    async def test_reporting_failure_logs_without_hiding_original(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        async def failing(request: Request) -> Response:
            raise ValueError("original")

        with pytest.raises(ValueError, match="original"):
            await AsyncErrorReportingMiddleware(_Reporter(fail=True)).handle(
                Request("GET", "/"), failing
            )
        assert len(caplog.records) == 1
        assert "private-reporter" not in caplog.text

    @pytest.mark.asyncio
    async def test_cancellation_is_not_reported(self) -> None:
        reporter = _Reporter()

        async def failing(request: Request) -> Response:
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await AsyncErrorReportingMiddleware(reporter).handle(
                Request("GET", "/"), failing
            )
        assert reporter.calls == []


class TestErrorEventID:
    @pytest.mark.parametrize("event_id", ["event-123", "a" * 128, None])
    def test_receipt_survives_scope_exit_without_changing_error_payload(
        self, event_id: str | None
    ) -> None:
        error = InvalidInputError(details={"field": "name"})
        original_args = error.args
        original_payload = default_error_envelope(
            error, 400, None, include_details=True
        )

        def failing(request: Request) -> Response:
            raise error

        with pytest.raises(InvalidInputError) as caught:
            ErrorReportingMiddleware(_Reporter(event_id=event_id)).handle(
                Request("GET", "/"), failing
            )
        assert caught.value is error
        assert get_error_event_id(error) == event_id
        assert error.args == original_args
        assert default_error_envelope(error, 400, None, include_details=True) == (
            original_payload
        )
        assert get_error_event_id(ValueError("unrelated")) is None

    @pytest.mark.parametrize("invalid_id", ["", "bad\nid", "é", "a" * 129, 123])
    def test_invalid_reporter_result_is_omitted_and_logged_safely(
        self,
        invalid_id: object,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        reporter = _Reporter()
        monkeypatch.setattr(reporter, "report", lambda exc, context: invalid_id)
        error = ValueError("original")

        def failing(request: Request) -> Response:
            raise error

        with pytest.raises(ValueError) as caught:
            ErrorReportingMiddleware(reporter).handle(Request("GET", "/"), failing)
        assert caught.value is error
        assert get_error_event_id(error) is None
        assert len(caplog.records) == 1
        assert caplog.records[0].exc_info is None
        assert caplog.records[0].getMessage() == (
            "Error reporting failed; preserving original exception"
        )
        assert "bad" not in caplog.text

    @pytest.mark.parametrize("failure", ["none", "reporter", "provider", "invalid"])
    def test_repeated_reporting_clears_previous_receipt(
        self, failure: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        error = ValueError("original")

        def failing(request: Request) -> Response:
            raise error

        with pytest.raises(ValueError):
            ErrorReportingMiddleware(_Reporter()).handle(Request("GET", "/"), failing)
        assert get_error_event_id(error) == "event"

        reporter = _Reporter(
            fail=failure == "reporter",
            event_id="bad id" if failure == "invalid" else None,
        )
        middleware = ErrorReportingMiddleware(
            reporter,
            context_provider=(
                (lambda _: {"unknown": "value"}) if failure == "provider" else None
            ),
        )
        with pytest.raises(ValueError) as caught:
            middleware.handle(Request("GET", "/"), failing)
        assert caught.value is error
        assert get_error_event_id(error) is None
        assert len(caplog.records) == (0 if failure == "none" else 1)

    def test_wrapped_exception_does_not_inherit_cause_event_id(self) -> None:
        error = ValueError("reported")

        def failing(request: Request) -> Response:
            raise error

        with pytest.raises(ValueError):
            ErrorReportingMiddleware(_Reporter()).handle(Request("GET", "/"), failing)
        wrapped = RuntimeError("wrapper")
        wrapped.__cause__ = error
        wrapped.__context__ = error
        assert get_error_event_id(error) == "event"
        assert get_error_event_id(wrapped) is None

    def test_unrecognized_private_metadata_is_not_published(self) -> None:
        error = ValueError()
        error.__dict__["_plynt_error_event"] = "unvalidated"
        assert get_error_event_id(error) is None

    def test_concurrent_threads_keep_receipts_on_their_own_errors(self) -> None:
        barrier = Barrier(2)

        def run(event_id: str) -> str | None:
            error = ValueError("failure")

            def failing(request: Request) -> Response:
                barrier.wait(timeout=5)
                raise error

            with pytest.raises(ValueError):
                ErrorReportingMiddleware(_Reporter(event_id=event_id)).handle(
                    Request("GET", "/"), failing
                )
            return get_error_event_id(error)

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(run, "thread-first")
            second = executor.submit(run, "thread-second")
            assert first.result(timeout=5) == "thread-first"
            assert second.result(timeout=5) == "thread-second"

    def test_metadata_failure_preserves_original_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        class RestrictedError(Exception):
            def __getattribute__(self, name: str) -> object:
                if name == "__dict__":
                    raise RuntimeError("private-metadata")
                return super().__getattribute__(name)

        error = RestrictedError()
        reporter = _Reporter()

        def failing(request: Request) -> Response:
            raise error

        with pytest.raises(RestrictedError) as caught:
            ErrorReportingMiddleware(reporter).handle(Request("GET", "/"), failing)
        assert caught.value is error
        assert reporter.calls == []
        assert len(caplog.records) == 1
        assert "private-metadata" not in caplog.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize("event_id", ["async-event", None, "bad id"])
    async def test_async_result_survives_scope_exit_and_validates_id(
        self, event_id: str | None, caplog: pytest.LogCaptureFixture
    ) -> None:
        error = ValueError("original")

        async def failing(request: Request) -> Response:
            raise error

        with pytest.raises(ValueError) as caught:
            await AsyncErrorReportingMiddleware(_Reporter(event_id=event_id)).handle(
                Request("GET", "/"), failing
            )
        assert caught.value is error
        assert get_error_event_id(error) == (None if event_id == "bad id" else event_id)
        assert len(caplog.records) == (1 if event_id == "bad id" else 0)

    @pytest.mark.asyncio
    async def test_concurrent_tasks_keep_receipts_on_their_own_errors(self) -> None:
        async def run(event_id: str) -> str | None:
            error = ValueError("failure")

            async def failing(request: Request) -> Response:
                await asyncio.sleep(0)
                raise error

            with pytest.raises(ValueError):
                await AsyncErrorReportingMiddleware(
                    _Reporter(event_id=event_id)
                ).handle(Request("GET", "/"), failing)
            return get_error_event_id(error)

        first, second = await asyncio.gather(run("task-first"), run("task-second"))
        assert first == "task-first"
        assert second == "task-second"

    @pytest.mark.asyncio
    async def test_cancelled_reporter_clears_stale_id_and_propagates(self) -> None:
        error = ValueError("original")

        async def failing(request: Request) -> Response:
            raise error

        middleware = AsyncErrorReportingMiddleware(_Reporter())
        with pytest.raises(ValueError):
            await middleware.handle(Request("GET", "/"), failing)
        assert get_error_event_id(error) == "event"

        class CancelledReporter(_Reporter):
            async def areport(
                self, exc: Exception, context: Mapping[str, object]
            ) -> str | None:
                raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await AsyncErrorReportingMiddleware(CancelledReporter()).handle(
                Request("GET", "/"), failing
            )
        assert get_error_event_id(error) is None
        assert get_retry_attempts() is None


class TestReportingContext:
    @pytest.mark.asyncio
    async def test_copied_task_context_does_not_mutate_parent_observations(
        self,
    ) -> None:
        async def observe_in_task() -> int | None:
            observe_retry_attempt()
            await asyncio.sleep(0)
            return get_retry_attempts()

        with reporting_scope():
            observe_retry_attempt()
            first, second = await asyncio.gather(observe_in_task(), observe_in_task())
            assert first == 2
            assert second == 2
            assert get_retry_attempts() == 1
        assert get_retry_attempts() is None

    def test_threads_keep_observed_attempts_separate(self) -> None:
        barrier = Barrier(2)

        def observe(count: int) -> int | None:
            with reporting_scope():
                for _ in range(count):
                    observe_retry_attempt()
                barrier.wait(timeout=5)
                return get_retry_attempts()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(observe, 1)
            second = executor.submit(observe, 3)
            assert first.result() == 1
            assert second.result() == 3
        assert get_retry_attempts() is None

    def test_nested_scopes_restore_counts_and_disabled_observation_retains_nothing(
        self,
    ) -> None:
        observe_retry_attempt()
        assert get_retry_attempts() is None
        with reporting_scope():
            observe_retry_attempt()
            with reporting_scope():
                assert get_retry_attempts() is None
                observe_retry_attempt()
                observe_retry_attempt()
                assert get_retry_attempts() == 2
            assert get_retry_attempts() == 1
        assert get_retry_attempts() is None
