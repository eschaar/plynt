"""Report sanitized error events using application-owned Sentry (ADR-0041)"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

try:
    import sentry_sdk
    from sentry_sdk.utils import event_from_exception
except ImportError as exc:
    raise ImportError(
        "Sentry reporting requires the optional dependency: install plynt[sentry]"
    ) from exc

if TYPE_CHECKING:  # pragma: no cover
    from sentry_sdk._types import Event, Hint

__all__ = ["SentryErrorReporter"]

_FRAME_FIELDS = {"filename", "function", "module", "lineno", "in_app"}


def _sanitize_event(event: "Event", hint: "Hint") -> "Event":
    """Remove automatic request data and sensitive exception diagnostics"""
    event.pop("request", None)
    event.pop("breadcrumbs", None)
    exceptions = event.get("exception", {}).get("values", [])
    for exception in exceptions:
        exception["value"] = "Exception reported by plynt"
        mechanism = exception.get("mechanism", {})
        mechanism.update(type="plynt", handled=True)
        mechanism.pop("data", None)
        exception["mechanism"] = mechanism
        for key in ("stacktrace", "raw_stacktrace"):
            stack = exception.get(key)
            if stack is not None:
                stack["frames"] = [
                    {key: value for key, value in frame.items() if key in _FRAME_FIELDS}
                    for frame in stack.get("frames", [])
                ]
    return event


class SentryErrorReporter:
    """Capture handled failures without initializing or flushing the Sentry SDK

    Applications own SDK configuration, sampling, and transport lifecycle.
    The current SDK scope is forked for each capture so plynt context does not
    leak into later events. SDK deduplication remains application-controlled.
    Exception messages, locals, source context, automatic request data, and
    breadcrumbs are omitted. Application-provided SDK metadata and callbacks
    remain the application's responsibility.

    """

    def report(self, exc: Exception, context: Mapping[str, object]) -> str | None:
        """Capture a sanitized event and return the SDK's optional event ID"""
        with sentry_sdk.new_scope() as scope:
            options = dict(scope.get_client().options)
            options.update(include_local_variables=False, add_full_stack=False)
            event, hint = event_from_exception(
                exc,
                client_options=options,
                mechanism={"type": "plynt", "handled": True},
            )
            event = _sanitize_event(event, hint)
            scope.set_context("plynt", dict(context))
            scope.add_event_processor(_sanitize_event)
            return scope.capture_event(event, hint=hint)

    async def areport(
        self, exc: Exception, context: Mapping[str, object]
    ) -> str | None:
        """Enqueue through the same SDK capture path without blocking on delivery"""
        return self.report(exc, context)
