"""Tests for plynth.http.errors (HttpStatusError)."""

from collections.abc import Callable
from http import HTTPStatus

import pytest

from plynth.base.errors import BaseError, StatusError
from plynth.http.errors import (
    BadRequestError,
    ConflictError,
    FeatureOfflineError,
    ForbiddenError,
    GoneError,
    HttpStatusError,
    InternalServerError,
    NotAllowedError,
    NotFoundError,
    OperationFailedError,
    RequestTimeoutError,
    ServiceUnavailableError,
    UnauthorizedError,
    UnprocessableEntityError,
    match_error,
)


class TestHttpStatusError:
    """Test suite for HttpStatusError."""

    def test_is_status_error(self) -> None:
        """Validate is status error."""
        err = HttpStatusError(status_code=404, method="GET", url="/items/1")
        assert isinstance(err, StatusError)

    def test_is_base_error(self) -> None:
        """Validate is base error."""
        err = HttpStatusError(status_code=404)
        assert isinstance(err, BaseError)

    def test_attributes_stored(self) -> None:
        """Validate attributes stored."""
        err = HttpStatusError(status_code=404, method="POST", url="/items")
        assert err.status_code == 404
        assert err.method == "POST"
        assert err.url == "/items"

    def test_method_and_url_in_details(self) -> None:
        """Validate method and url in details."""
        err = HttpStatusError(status_code=404, method="GET", url="/items/1")
        assert err.details is not None
        assert err.details["method"] == "GET"
        assert err.details["url"] == "/items/1"
        assert err.details["status_code"] == 404

    def test_default_code(self) -> None:
        """Validate default code."""
        err = HttpStatusError(status_code=500, method="GET", url="/")
        assert err.code == "HTTP_STATUS_ERROR"

    def test_custom_message(self) -> None:
        """Validate custom message."""
        err = HttpStatusError(
            "Not found", status_code=404, method="GET", url="/items/1"
        )
        assert err.message == "Not found"

    def test_to_dict(self) -> None:
        """Validate to dict."""
        err = HttpStatusError(status_code=503, method="POST", url="/jobs")
        d = err.to_dict()
        assert d["code"] == "HTTP_STATUS_ERROR"
        assert d["details"]["status_code"] == 503
        assert d["details"]["method"] == "POST"
        assert d["details"]["url"] == "/jobs"

    def test_method_and_url_are_optional(self) -> None:
        # method and url default to empty string; only status_code is required
        """Validate method and url are optional."""
        err = HttpStatusError(status_code=404)
        assert err.method == ""
        assert err.url == ""
        assert err.status_code == 404

    def test_response_defaults_to_none(self) -> None:
        """Validate response defaults to none."""
        err = HttpStatusError(status_code=404, method="GET", url="/items/1")
        assert err._response is None


class TestHttpStatusSubclasses:
    """Test that HTTP status error subclasses carry correct metadata."""

    @pytest.mark.parametrize(
        "cls,expected_status,expected_code",
        [
            (BadRequestError, HTTPStatus.BAD_REQUEST.value, "BAD_REQUEST"),
            (UnauthorizedError, HTTPStatus.UNAUTHORIZED.value, "UNAUTHORIZED"),
            (ForbiddenError, HTTPStatus.FORBIDDEN.value, "FORBIDDEN"),
            (NotFoundError, HTTPStatus.NOT_FOUND.value, "NOT_FOUND"),
            (NotAllowedError, HTTPStatus.METHOD_NOT_ALLOWED.value, "NOT_ALLOWED"),
            (RequestTimeoutError, HTTPStatus.REQUEST_TIMEOUT.value, "TIMEOUT"),
            (ConflictError, HTTPStatus.CONFLICT.value, "CONFLICT"),
            (GoneError, HTTPStatus.GONE.value, "GONE"),
            (
                UnprocessableEntityError,
                HTTPStatus.UNPROCESSABLE_ENTITY.value,
                "UNPROCESSABLE_ENTITY",
            ),
            (
                InternalServerError,
                HTTPStatus.INTERNAL_SERVER_ERROR.value,
                "INTERNAL_SERVER_ERROR",
            ),
            (
                OperationFailedError,
                HTTPStatus.INTERNAL_SERVER_ERROR.value,
                "OPERATION_FAILED",
            ),
            (
                ServiceUnavailableError,
                HTTPStatus.SERVICE_UNAVAILABLE.value,
                "SERVICE_UNAVAILABLE",
            ),
            (
                FeatureOfflineError,
                HTTPStatus.SERVICE_UNAVAILABLE.value,
                "FEATURE_OFFLINE",
            ),
        ],
    )
    def test_status_code_and_error_code(
        self,
        cls: Callable[[], HttpStatusError],
        expected_status: int,
        expected_code: str,
    ) -> None:
        """Validate status code and error code."""
        err = cls()
        assert err.status_code == expected_status
        assert err.code == expected_code

    def test_all_subclasses_are_http_status_errors(self) -> None:
        """Validate all subclasses are http status errors."""
        subclasses = [
            BadRequestError,
            UnauthorizedError,
            ForbiddenError,
            NotFoundError,
            NotAllowedError,
            RequestTimeoutError,
            ConflictError,
            GoneError,
            UnprocessableEntityError,
            InternalServerError,
            OperationFailedError,
            ServiceUnavailableError,
            FeatureOfflineError,
        ]
        for cls in subclasses:
            assert issubclass(cls, HttpStatusError), (
                f"{cls.__name__} must extend HttpStatusError"
            )

    def test_method_and_url_default_to_empty_string(self) -> None:
        """Validate method and url default to empty string."""
        err = NotFoundError()
        assert err.method == ""
        assert err.url == ""

    def test_method_and_url_with_context(self) -> None:
        """Validate method and url with context."""
        err = NotFoundError(method="GET", url="/items/1")
        assert err.method == "GET"
        assert err.url == "/items/1"

    def test_custom_message_overrides_default(self) -> None:
        """Validate custom message overrides default."""
        err = BadRequestError("Missing required field")
        assert err.message == "Missing required field"

    def test_default_message_is_non_empty(self) -> None:
        """Validate default message is non empty."""
        err = BadRequestError()
        assert err.message

    def test_error_is_catchable_as_http_status_error(self) -> None:
        """Validate error is catchable as http status error."""
        with pytest.raises(HttpStatusError):
            raise NotFoundError(method="GET", url="/items/1")

    def test_bad_request(self) -> None:
        """Validate bad request."""
        err = BadRequestError()
        assert err.status_code == HTTPStatus.BAD_REQUEST.value
        assert err.code == "BAD_REQUEST"

    def test_unauthorized(self) -> None:
        """Validate unauthorized."""
        err = UnauthorizedError()
        assert err.status_code == HTTPStatus.UNAUTHORIZED.value
        assert err.code == "UNAUTHORIZED"

    def test_forbidden(self) -> None:
        """Validate forbidden."""
        err = ForbiddenError()
        assert err.status_code == HTTPStatus.FORBIDDEN.value
        assert err.code == "FORBIDDEN"

    def test_not_allowed(self) -> None:
        """Validate not allowed."""
        err = NotAllowedError()
        assert err.status_code == HTTPStatus.METHOD_NOT_ALLOWED.value
        assert err.code == "NOT_ALLOWED"

    def test_timeout(self) -> None:
        """Validate timeout."""
        err = RequestTimeoutError()
        assert err.status_code == HTTPStatus.REQUEST_TIMEOUT.value
        assert err.code == "TIMEOUT"

    def test_conflict(self) -> None:
        """Validate conflict."""
        err = ConflictError()
        assert err.status_code == HTTPStatus.CONFLICT.value
        assert err.code == "CONFLICT"

    def test_gone(self) -> None:
        """Validate gone."""
        err = GoneError()
        assert err.status_code == HTTPStatus.GONE.value
        assert err.code == "GONE"

    def test_not_found(self) -> None:
        """Validate not found."""
        err = NotFoundError()
        assert err.status_code == HTTPStatus.NOT_FOUND.value
        assert err.code == "NOT_FOUND"

    def test_unprocessable_entity(self) -> None:
        """Validate unprocessable entity."""
        err = UnprocessableEntityError()
        assert err.status_code == HTTPStatus.UNPROCESSABLE_ENTITY.value
        assert err.code == "UNPROCESSABLE_ENTITY"

    def test_feature_offline(self) -> None:
        """Validate feature offline."""
        err = FeatureOfflineError()
        assert err.status_code == HTTPStatus.SERVICE_UNAVAILABLE.value
        assert err.code == "FEATURE_OFFLINE"

    def test_service_unavailable(self) -> None:
        """Validate service unavailable."""
        err = ServiceUnavailableError()
        assert err.status_code == HTTPStatus.SERVICE_UNAVAILABLE.value
        assert err.code == "SERVICE_UNAVAILABLE"

    def test_internal_server_error(self) -> None:
        """Validate internal server error."""
        err = InternalServerError()
        assert err.status_code == HTTPStatus.INTERNAL_SERVER_ERROR.value
        assert err.code == "INTERNAL_SERVER_ERROR"

    def test_operation_failed(self) -> None:
        """Validate operation failed."""
        err = OperationFailedError()
        assert err.status_code == HTTPStatus.INTERNAL_SERVER_ERROR.value
        assert err.code == "OPERATION_FAILED"


class TestMatchError:
    """Test the match_error() factory function."""

    @pytest.mark.parametrize(
        "status_code,expected_cls",
        [
            (400, BadRequestError),
            (401, UnauthorizedError),
            (403, ForbiddenError),
            (404, NotFoundError),
            (405, NotAllowedError),
            (408, RequestTimeoutError),
            (409, ConflictError),
            (410, GoneError),
            (422, UnprocessableEntityError),
            (500, InternalServerError),
            (503, ServiceUnavailableError),
        ],
    )
    def test_known_status_codes_return_named_class(
        self, status_code: int, expected_cls: type[HttpStatusError]
    ) -> None:
        """Validate known status codes return named class."""
        err = match_error(status_code)
        assert isinstance(err, expected_cls)
        assert err.status_code == status_code

    def test_unknown_status_code_falls_back_to_base(self) -> None:
        """Validate unknown status code falls back to base."""
        err = match_error(418)
        assert type(err) is HttpStatusError
        assert err.status_code == 418

    def test_passes_method_and_url(self) -> None:
        """Validate passes method and url."""
        err = match_error(404, method="DELETE", url="/items/99")
        assert err.method == "DELETE"
        assert err.url == "/items/99"

    def test_passes_custom_message(self) -> None:
        """Validate passes custom message."""
        err = match_error(400, message="Bad input")
        assert err.message == "Bad input"

    def test_fallback_carries_status_code(self) -> None:
        """Validate fallback carries status code."""
        err = match_error(429, method="POST", url="/submit")
        assert err.status_code == 429
        assert err.method == "POST"
        assert err.url == "/submit"

    def test_result_is_catchable_as_http_status_error(self) -> None:
        """Validate result is catchable as http status error."""
        with pytest.raises(HttpStatusError):
            raise match_error(503)
