"""Verify Sentry captures with an in-memory transport and no network calls"""

import asyncio
import importlib
import json
import sys
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest

sentry_sdk = pytest.importorskip("sentry_sdk")

from sentry_sdk import Client  # noqa: E402
from sentry_sdk.envelope import Envelope  # noqa: E402
from sentry_sdk.integrations.dedupe import DedupeIntegration  # noqa: E402
from sentry_sdk.transport import Transport  # noqa: E402

from plynt.base import (  # noqa: E402
    ErrorReporter,
    Request,
    Response,
    get_error_event_id,
)
from plynt.integrations.sentry import SentryErrorReporter  # noqa: E402
from plynt.middleware import (  # noqa: E402
    AsyncErrorReportingMiddleware,
    ErrorReportingMiddleware,
)

if TYPE_CHECKING:
    from sentry_sdk._types import Event


class _Transport(Transport):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[Event] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        event = envelope.get_event()
        if event is not None:
            self.events.append(event)


@pytest.fixture
def capture() -> Generator[tuple[Client, _Transport], None, None]:
    transport = _Transport()
    client = Client(
        dsn="https://public@example.invalid/1",
        transport=transport,
        default_integrations=False,
        integrations=[DedupeIntegration()],
        release="application-release",
        environment="test",
        include_local_variables=True,
    )
    with sentry_sdk.isolation_scope():
        with sentry_sdk.new_scope() as scope:
            scope.set_client(client)
            yield client, transport
    client.close()


class TestSentryErrorReporter:
    def test_constructor_never_initializes_sdk(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def forbidden(*args: object, **kwargs: object) -> None:
            pytest.fail("Applications, not reporters, initialize Sentry")

        monkeypatch.setattr(sentry_sdk, "init", forbidden)
        assert isinstance(SentryErrorReporter(), ErrorReporter)

    def test_captures_redacted_exception_chain_and_preserves_application_scope(
        self, capture: tuple[Client, _Transport]
    ) -> None:
        _, transport = capture
        scope = sentry_sdk.get_current_scope()
        scope.set_tag("application", "example")
        scope.set_context("plynt", {"previous": True})
        scope.set_context("application", {"component": "api"})
        scope.set_extra("application", "safe")
        sentry_sdk.add_breadcrumb(message="private-breadcrumb")
        scope.add_event_processor(
            lambda event, hint: {
                **event,
                "request": {
                    "headers": {"Authorization": "private-header"},
                    "data": "private-body",
                    "query_string": "token=private-query",
                },
            }
        )

        def add_unsafe_exception_data(event: "Event", hint: object) -> "Event":
            if "exception" not in event:
                return event
            exception = event["exception"]["values"][0]
            exception["mechanism"]["data"] = {"value": "private-mechanism"}
            exception["raw_stacktrace"] = {
                "frames": [
                    {
                        "function": "fetch",
                        "lineno": 1,
                        "vars": {"token": "private-local"},
                        "context_line": "private-source",
                        "abs_path": "/private-path",
                    }
                ]
            }
            return event

        scope.add_event_processor(add_unsafe_exception_data)
        try:
            try:
                raise ValueError("private-cause")
            except ValueError as cause:
                raise RuntimeError("private-error") from cause
        except RuntimeError as error:
            event_id = SentryErrorReporter().report(
                error, {"connector": "example", "url": "/safe", "attempts": 2}
            )
        assert event_id is not None
        assert len(transport.events) == 1
        event = transport.events[0]
        assert event["event_id"] == event_id
        assert event["release"] == "application-release"
        assert event["environment"] == "test"
        assert event["tags"]["application"] == "example"
        assert event["contexts"]["application"] == {"component": "api"}
        assert event["contexts"]["plynt"] == {
            "connector": "example",
            "url": "/safe",
            "attempts": 2,
        }
        assert event["extra"]["application"] == "safe"
        assert "private-" not in json.dumps(event)
        assert "request" not in event
        assert "breadcrumbs" not in event
        exceptions = event["exception"]["values"]
        assert len(exceptions) == 2
        assert {item["type"] for item in exceptions} == {"ValueError", "RuntimeError"}
        assert all(item["mechanism"]["handled"] is True for item in exceptions)
        assert all(item["mechanism"]["type"] == "plynt" for item in exceptions)
        assert any(item["stacktrace"]["frames"] for item in exceptions)
        for exception in exceptions:
            for stack_name in ("stacktrace", "raw_stacktrace"):
                for frame in exception.get(stack_name, {}).get("frames", []):
                    assert set(frame) <= {
                        "filename",
                        "function",
                        "module",
                        "lineno",
                        "in_app",
                    }
        assert sentry_sdk.get_current_scope() is scope
        sentry_sdk.capture_message("later")
        later = transport.events[-1]
        assert later["contexts"]["plynt"] == {"previous": True}
        assert later["request"]["data"] == "private-body"
        breadcrumbs = later["breadcrumbs"]
        assert isinstance(breadcrumbs, dict)
        assert breadcrumbs["values"][0]["message"] == "private-breadcrumb"

    @pytest.mark.parametrize("async_reporting", [False, True])
    def test_middleware_publishes_actual_sdk_id(
        self, capture: tuple[Client, _Transport], async_reporting: bool
    ) -> None:
        _, transport = capture
        error = ValueError("private-error")

        def failing(request: Request) -> Response:
            raise error

        async def async_failing(request: Request) -> Response:
            return failing(request)

        async def run() -> None:
            await AsyncErrorReportingMiddleware(SentryErrorReporter()).handle(
                Request("GET", "/safe"), async_failing
            )

        with pytest.raises(ValueError) as caught:
            if async_reporting:
                asyncio.run(run())
            else:
                ErrorReportingMiddleware(SentryErrorReporter()).handle(
                    Request("GET", "/safe"), failing
                )
        assert caught.value is error
        assert len(transport.events) == 1
        assert get_error_event_id(error) == transport.events[0]["event_id"]
        assert "private-error" not in json.dumps(transport.events)

    def test_sdk_dedupe_drops_automatic_recapture_of_same_exception(
        self, capture: tuple[Client, _Transport]
    ) -> None:
        _, transport = capture
        error = ValueError("failure")
        event_id = SentryErrorReporter().report(error, {"operation": "fetch"})
        assert event_id is not None
        assert sentry_sdk.capture_exception(error) is None
        assert len(transport.events) == 1

    def test_different_exceptions_and_contexts_are_not_deduplicated(
        self, capture: tuple[Client, _Transport]
    ) -> None:
        _, transport = capture
        reporter = SentryErrorReporter()
        first = reporter.report(ValueError("one"), {"operation": "first"})
        second = reporter.report(ValueError("two"), {"operation": "second"})
        assert first is not None
        assert second is not None
        assert first != second
        assert [event["contexts"]["plynt"] for event in transport.events] == [
            {"operation": "first"},
            {"operation": "second"},
        ]

    def test_uninitialized_sdk_does_not_invent_id(self) -> None:
        with sentry_sdk.isolation_scope():
            with sentry_sdk.new_scope() as scope:
                scope.set_client(Client(default_integrations=False))
                assert SentryErrorReporter().report(ValueError(), {}) is None

    def test_application_before_send_can_drop_event(
        self, capture: tuple[Client, _Transport]
    ) -> None:
        client, transport = capture
        client.options["before_send"] = lambda event, hint: None
        assert SentryErrorReporter().report(ValueError(), {}) is None
        assert transport.events == []

    def test_capture_failures_propagate_to_middleware_boundary(
        self, capture: tuple[Client, _Transport], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def failing(
            self: object, event: object, hint: object = None, **kwargs: object
        ) -> str | None:
            raise RuntimeError("private-capture")

        monkeypatch.setattr(sentry_sdk.Scope, "capture_event", failing)
        with pytest.raises(RuntimeError, match="private-capture"):
            SentryErrorReporter().report(ValueError(), {})

    def test_missing_extra_gives_actionable_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module_name = "plynt.integrations.sentry"
        existing = sys.modules.pop(module_name)
        try:
            monkeypatch.setitem(sys.modules, "sentry_sdk", None)
            with pytest.raises(ImportError, match=r"plynt\[sentry\]"):
                importlib.import_module(module_name)
        finally:
            sys.modules[module_name] = existing
