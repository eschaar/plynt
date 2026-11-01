"""Verify structural sync/async reporting without a vendor dependency"""

from collections.abc import Mapping

import pytest

from plynt.base import ErrorReporter


class _Reporter:
    def __init__(self, event_id: str | None) -> None:
        self.event_id = event_id
        self.calls: list[tuple[Exception, Mapping[str, object]]] = []

    def report(self, exc: Exception, context: Mapping[str, object]) -> str | None:
        self.calls.append((exc, context))
        return self.event_id

    async def areport(
        self, exc: Exception, context: Mapping[str, object]
    ) -> str | None:
        return self.report(exc, context)


class TestErrorReporter:
    @pytest.mark.parametrize("event_id", ["event-123", None])
    def test_sync_implementation_receives_original_error_and_context(
        self, event_id: str | None
    ) -> None:
        implementation = _Reporter(event_id)
        reporter: ErrorReporter = implementation
        error = ValueError("failure")
        context: dict[str, object] = {"operation": "fetch", "status": 503}
        assert isinstance(reporter, ErrorReporter)
        assert reporter.report(error, context) == event_id
        assert implementation.calls == [(error, context)]
        assert implementation.calls[0][0] is error
        assert implementation.calls[0][1] is context

    @pytest.mark.asyncio
    @pytest.mark.parametrize("event_id", ["event-123", None])
    async def test_async_implementation_preserves_event_id_contract(
        self, event_id: str | None
    ) -> None:
        implementation = _Reporter(event_id)
        reporter: ErrorReporter = implementation
        error = ValueError("failure")
        context: dict[str, object] = {"operation": "fetch"}
        assert await reporter.areport(error, context) == event_id
        assert implementation.calls == [(error, context)]

    def test_unrelated_object_does_not_satisfy_protocol(self) -> None:
        assert not isinstance(object(), ErrorReporter)
