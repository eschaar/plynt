"""Report chain failures without replacing their exceptions (ADR-0041/0042)"""

import logging
from collections.abc import Callable, Mapping
from urllib.parse import urlsplit, urlunsplit

from plynt.base import (
    AuthenticationError,
    ErrorReporter,
    Request,
    Response,
    StatusError,
)
from plynt.base.error_reporter import _set_error_event_id
from plynt.base.middleware import NextAsyncHandler, NextSyncHandler
from plynt.base.reporting_context import get_retry_attempts, reporting_scope
from plynt.base.request_id import RequestIDPolicy
from plynt.middleware.logging import _scrub_url

__all__ = ["AsyncErrorReportingMiddleware", "ErrorReportingMiddleware"]

_logger = logging.getLogger(__name__)
_id_policy = RequestIDPolicy()


def _safe_request_url(url: str) -> str | None:
    """Return a redacted URL or log and omit malformed input"""
    try:
        split = urlsplit(url)
        safe_url = urlunsplit(
            (split.scheme, split.netloc.rsplit("@", 1)[-1], split.path, split.query, "")
        )
        return _scrub_url(safe_url)
    except ValueError:
        _logger.error("Invalid request URL omitted from error reporting context")
        return None


class _ReportingBase:
    def __init__(
        self,
        reporter: ErrorReporter,
        *,
        context_provider: Callable[[Request], Mapping[str, str]] | None = None,
    ) -> None:
        self._reporter = reporter
        self._context_provider = context_provider

    def _context(self, request: Request, exc: Exception) -> dict[str, object]:
        """Build redacted request context and explicitly supplied domain fields"""
        context: dict[str, object] = {"method": request.method}
        safe_url = _safe_request_url(request.url)
        if safe_url is not None:
            context["url"] = safe_url
        context.update(self._domain_context(request))
        attempts = get_retry_attempts()
        if attempts is not None:
            context.update(attempts=attempts, retries=attempts - 1)
        if isinstance(exc, (StatusError, AuthenticationError)):
            context["upstream_status"] = exc.status_code
        response = getattr(exc, "response", None)
        if isinstance(response, Response):
            for name, value in response.headers.items():
                if name.lower() == "x-request-id" and _id_policy._is_valid(value):
                    context["upstream_request_id"] = value
                    break
        return context

    def _domain_context(self, request: Request) -> dict[str, str]:
        """Validate explicitly supplied domain identifiers"""
        context: dict[str, str] = {}
        if self._context_provider is not None:
            provided = self._context_provider(request)
            for key, value in provided.items():
                if key not in {"connector", "service", "operation"}:
                    raise ValueError("Unsupported error reporting context field")
                if (
                    not isinstance(value, str)
                    or not value
                    or not value.isprintable()
                    or len(value) > 128
                ):
                    raise ValueError("Invalid error reporting context value")
                context[key] = value
        return context


class ErrorReportingMiddleware(_ReportingBase):
    """Report synchronous chain exceptions with safe context

    Place outside retry middleware. Domain fields must be safe identifiers,
    never credentials or personal data. Provider/reporter failures are logged
    safely and cannot replace the original exception. Returned error statuses
    and failures during later stream iteration are not reported here.

    """

    def handle(self, request: Request, next_handler: NextSyncHandler) -> Response:
        """Report a raised exception once and preserve its identity"""
        with reporting_scope():
            try:
                return next_handler(request)
            except Exception as exc:
                try:
                    _set_error_event_id(exc, None)
                    event_id = self._reporter.report(exc, self._context(request, exc))
                    _set_error_event_id(exc, event_id)
                except Exception:
                    _logger.error(
                        "Error reporting failed; preserving original exception"
                    )
                raise


class AsyncErrorReportingMiddleware(_ReportingBase):
    """Report async chain exceptions using the same redacted context rules"""

    async def handle(
        self, request: Request, next_handler: NextAsyncHandler
    ) -> Response:
        """Await reporting once and preserve the original chain exception"""
        with reporting_scope():
            try:
                return await next_handler(request)
            except Exception as exc:
                try:
                    _set_error_event_id(exc, None)
                    event_id = await self._reporter.areport(
                        exc, self._context(request, exc)
                    )
                    _set_error_event_id(exc, event_id)
                except Exception:
                    _logger.error(
                        "Error reporting failed; preserving original exception"
                    )
                raise
