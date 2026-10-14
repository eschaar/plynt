"""HTTP-specific status errors.

Error hierarchy:

    TransportError (base.errors)
    └── StatusError (base.errors) — response status indicated failure
        └── HttpStatusError — HTTP-specific: carries method and URL
            ├── BadRequestError          (400)
            ├── UnauthorizedError        (401)
            ├── ForbiddenError           (403)
            ├── NotFoundError            (404)
            ├── NotAllowedError          (405)
            ├── RequestTimeoutError      (408)
            ├── ConflictError            (409)
            ├── GoneError                (410)
            ├── UnprocessableEntityError (422)
            ├── InternalServerError      (500)
            ├── OperationFailedError     (500)
            ├── ServiceUnavailableError  (503)
            └── FeatureOfflineError      (503)
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from plynt.base.errors import StatusError
from plynt.base.response import Response

__all__ = [
    "BadRequestError",
    "ConflictError",
    "FeatureOfflineError",
    "ForbiddenError",
    "GoneError",
    "HttpStatusError",
    "InternalServerError",
    "NotAllowedError",
    "NotFoundError",
    "OperationFailedError",
    "RequestTimeoutError",
    "ServiceUnavailableError",
    "StatusError",
    "UnauthorizedError",
    "UnprocessableEntityError",
    "match_error",
]


class HttpStatusError(StatusError):
    """Raised when an HTTP response status code indicates failure.

    Extends ``StatusError`` with HTTP-specific context: the request method
    and URL. This information is essential for useful error logging and
    debugging.

    Attributes:
        status_code: HTTP status code (e.g. ``404``, ``500``).
        method: HTTP method of the request (e.g. ``"GET"``, ``"POST"``).
        url: URL of the request that produced this response.

    Example:
        raise HttpStatusError(status_code=404, method="GET", url="https://api.example.com/items/1")
        raise HttpStatusError("Not found", status_code=404, method="GET",
                                url="/items/1")

    """

    code = "HTTP_STATUS_ERROR"
    message = "HTTP response status indicates failure"

    def __init__(
        self,
        message: str | None = None,
        *,
        status_code: int,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialise an HttpStatusError.

        Args:
            message: Human-readable description. Falls back to the class
                default if omitted.
            status_code: HTTP status code returned by the server.
            method: HTTP method of the originating request. Defaults to an
                empty string when the request context is unavailable.
            url: URL of the originating request. Defaults to an empty string
                when the request context is unavailable.
            **kwargs: Additional key-value pairs merged into ``details``.

        """
        super().__init__(
            message, status_code=status_code, method=method, url=url, **kwargs
        )
        self.method = method
        self.url = url
        self._response: Response | None = None

    @property
    def response(self) -> Response | None:
        """Return the optional transport response associated with this error."""
        return self._response

    def attach_response(self, response: Response) -> None:
        """Attach the originating response object to this HTTP status error."""
        self._response = response


class BadRequestError(HttpStatusError):
    """Raised when the server cannot process the request due to a client
    error (HTTP 400).
    """

    code = "BAD_REQUEST"
    message = HTTPStatus.BAD_REQUEST.phrase

    def __init__(
        self,
        message: str | None = None,
        *,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize BadRequestError."""
        super().__init__(
            message,
            status_code=HTTPStatus.BAD_REQUEST.value,
            method=method,
            url=url,
            **kwargs,
        )


class UnauthorizedError(HttpStatusError):
    """Raised when authentication is required or has failed (HTTP 401)."""

    code = "UNAUTHORIZED"
    message = "Authentication required"

    def __init__(
        self,
        message: str | None = None,
        *,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize UnauthorizedError."""
        super().__init__(
            message,
            status_code=HTTPStatus.UNAUTHORIZED.value,
            method=method,
            url=url,
            **kwargs,
        )


class ForbiddenError(HttpStatusError):
    """Raised when the server refuses to authorise the request (HTTP 403)."""

    code = "FORBIDDEN"
    message = HTTPStatus.FORBIDDEN.phrase

    def __init__(
        self,
        message: str | None = None,
        *,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize ForbiddenError."""
        super().__init__(
            message,
            status_code=HTTPStatus.FORBIDDEN.value,
            method=method,
            url=url,
            **kwargs,
        )


class NotFoundError(HttpStatusError):
    """Raised when the requested resource could not be found (HTTP 404)."""

    code = "NOT_FOUND"
    message = "Resource not found"

    def __init__(
        self,
        message: str | None = None,
        *,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize NotFoundError."""
        super().__init__(
            message,
            status_code=HTTPStatus.NOT_FOUND.value,
            method=method,
            url=url,
            **kwargs,
        )


class NotAllowedError(HttpStatusError):
    """Raised when the HTTP method is not allowed for the requested URL (HTTP 405)."""

    code = "NOT_ALLOWED"
    message = HTTPStatus.METHOD_NOT_ALLOWED.phrase

    def __init__(
        self,
        message: str | None = None,
        *,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize NotAllowedError."""
        super().__init__(
            message,
            status_code=HTTPStatus.METHOD_NOT_ALLOWED.value,
            method=method,
            url=url,
            **kwargs,
        )


class RequestTimeoutError(HttpStatusError):
    """Raised when the server timed out waiting for the request (HTTP 408)."""

    code = "TIMEOUT"
    message = HTTPStatus.REQUEST_TIMEOUT.phrase

    def __init__(
        self,
        message: str | None = None,
        *,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize RequestTimeoutError."""
        super().__init__(
            message,
            status_code=HTTPStatus.REQUEST_TIMEOUT.value,
            method=method,
            url=url,
            **kwargs,
        )


class ConflictError(HttpStatusError):
    """Raised when the request conflicts with the current resource state (HTTP 409)."""

    code = "CONFLICT"
    message = HTTPStatus.CONFLICT.phrase

    def __init__(
        self,
        message: str | None = None,
        *,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize ConflictError."""
        super().__init__(
            message,
            status_code=HTTPStatus.CONFLICT.value,
            method=method,
            url=url,
            **kwargs,
        )


class GoneError(HttpStatusError):
    """Raised when the requested resource has been permanently removed (HTTP 410)."""

    code = "GONE"
    message = HTTPStatus.GONE.phrase

    def __init__(
        self,
        message: str | None = None,
        *,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize GoneError."""
        super().__init__(
            message, status_code=HTTPStatus.GONE.value, method=method, url=url, **kwargs
        )


class UnprocessableEntityError(HttpStatusError):
    """Raised when the server cannot process the request entity (HTTP 422)."""

    code = "UNPROCESSABLE_ENTITY"
    message = "Unprocessable entity"

    def __init__(
        self,
        message: str | None = None,
        *,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize UnprocessableEntityError."""
        super().__init__(
            message,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY.value,
            method=method,
            url=url,
            **kwargs,
        )


class InternalServerError(HttpStatusError):
    """Raised when the server encountered an unexpected condition (HTTP 500)."""

    code = "INTERNAL_SERVER_ERROR"
    message = "Internal server error"

    def __init__(
        self,
        message: str | None = None,
        *,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize InternalServerError."""
        super().__init__(
            message,
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            method=method,
            url=url,
            **kwargs,
        )


class OperationFailedError(HttpStatusError):
    """Raised for generic server-side failures not covered by other error
    types (HTTP 500).
    """

    code = "OPERATION_FAILED"
    message = "Operation failed"

    def __init__(
        self,
        message: str | None = None,
        *,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize OperationFailedError."""
        super().__init__(
            message,
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            method=method,
            url=url,
            **kwargs,
        )


class ServiceUnavailableError(HttpStatusError):
    """Raised when the service is temporarily unavailable (HTTP 503)."""

    code = "SERVICE_UNAVAILABLE"
    message = "Service unavailable"

    def __init__(
        self,
        message: str | None = None,
        *,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize ServiceUnavailableError."""
        super().__init__(
            message,
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.value,
            method=method,
            url=url,
            **kwargs,
        )


class FeatureOfflineError(HttpStatusError):
    """Raised when a feature is intentionally unavailable (HTTP 503)."""

    code = "FEATURE_OFFLINE"
    message = "Requested feature is offline"

    def __init__(
        self,
        message: str | None = None,
        *,
        method: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize FeatureOfflineError."""
        super().__init__(
            message,
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.value,
            method=method,
            url=url,
            **kwargs,
        )


# Maps HTTP status codes to the most specific named error class.
# Where two classes share a code (500, 503), the more generic class is preferred.
_STATUS_CODE_MAP: dict[int, type[HttpStatusError]] = {
    400: BadRequestError,
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
    405: NotAllowedError,
    408: RequestTimeoutError,
    409: ConflictError,
    410: GoneError,
    422: UnprocessableEntityError,
    500: InternalServerError,
    503: ServiceUnavailableError,
}


def match_error(
    status_code: int,
    *,
    method: str = "",
    url: str = "",
    message: str | None = None,
    **kwargs: Any,
) -> HttpStatusError:
    """Return the most specific ``HttpStatusError`` subclass for a status code.

    Looks up a named error class by status code, instantiates it, and returns
    the result. Falls back to plain ``HttpStatusError`` for unrecognised codes.

    Example:
        err = match_error(404, method="GET", url="/items/1")
        assert isinstance(err, NotFoundError)

    """
    cls = _STATUS_CODE_MAP.get(status_code)
    if cls is not None:
        return cls(message, method=method, url=url, **kwargs)
    return HttpStatusError(
        message, status_code=status_code, method=method, url=url, **kwargs
    )
