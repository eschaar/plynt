from typing import Any

import pytest

from plynth.base.errors import (
    BaseError,
    DependencyUnavailableError,
    FeatureDisabledError,
    InvalidInputError,
    OperationFailedError,
)
from plynth.http.errors import (
    BadRequestError,
    HttpStatusError,
    InternalServerError,
    ServiceUnavailableError,
)
from plynth.http.mapping import APIErrorMapper


class DummyError(BaseError):
    """Represent DummyError."""

    pass


class TestAPIErrorMapper:
    """Tests for APIErrorMapper error mapping logic.

    Ensures that core errors are mapped to the correct HTTP error subclasses.
    """

    @pytest.mark.parametrize(
        "err_cls, message, expected_cls",
        [
            (InvalidInputError, "bad", BadRequestError),
            (FeatureDisabledError, "off", ServiceUnavailableError),
            (DependencyUnavailableError, "dep", ServiceUnavailableError),
            (DummyError, "dummy", InternalServerError),
        ],
    )
    def test_api_error_mapper_param(
        self,
        err_cls: type[BaseError],
        message: str,
        expected_cls: type[HttpStatusError],
    ) -> None:
        """Verify that a core error maps to the expected HTTP error subclass."""
        err = err_cls(message=message)
        mapped = APIErrorMapper.to_mapped_error(err)
        assert isinstance(mapped, expected_cls)
        assert mapped.message == message

    @pytest.mark.parametrize(
        "kwargs, expected_code, expected_details",
        [
            ({"code": "FOO", "details": {"x": 1}}, "FOO", {"x": 1}),
            (
                {"code": "BAR", "details": {"a": 2}, "extra": 42},
                "BAR",
                {"a": 2, "extra": 42},
            ),
        ],
    )
    def test_api_error_mapper_kwargs(
        self,
        kwargs: dict[str, Any],
        expected_code: str,
        expected_details: dict[str, Any],
    ) -> None:
        """Verify that code, details, and extra kwargs are forwarded correctly."""
        err = InvalidInputError(message="bad", **kwargs)
        mapped = APIErrorMapper.to_mapped_error(err)
        assert mapped.code == expected_code
        assert mapped.details is not None
        for k, v in expected_details.items():
            assert mapped.details[k] == v

    @pytest.mark.parametrize("err_cls", [DummyError])
    def test_api_error_mapper_fallback_type(self, err_cls: type[BaseError]) -> None:
        """Fallback for unrecognised errors is InternalServerError."""
        err = err_cls(message="strange")
        mapped = APIErrorMapper.to_mapped_error(err)
        assert isinstance(mapped, HttpStatusError)
        assert mapped.message == "strange"

    def test_api_error_mapper_operation_failed_fallback(self) -> None:
        """Core OperationFailedError falls back to InternalServerError."""
        err = OperationFailedError(message="fail")
        mapped = APIErrorMapper.to_mapped_error(err)
        assert type(mapped) is InternalServerError
        assert mapped.message == "fail"
