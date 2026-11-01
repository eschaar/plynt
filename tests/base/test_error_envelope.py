"""Verify safe external error envelopes and custom callable fallback"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import cast

import pytest

from plynt.base import (
    AuthenticationError,
    BaseError,
    ErrorEnvelope,
    InvalidInputError,
    build_error_envelope,
    default_error_envelope,
)


class TestDefaultErrorEnvelope:
    def test_base_error_keeps_existing_message_and_code_payload(self) -> None:
        error = InvalidInputError(details={"field": "name"})
        assert default_error_envelope(error, 400, "request-123") == {
            "message": "Invalid input data",
            "code": "INVALID_INPUT",
        }

    def test_missing_code_uses_existing_internal_error_code(self) -> None:
        assert default_error_envelope(BaseError("custom"), 500, None) == {
            "message": "custom",
            "code": "INTERNAL_SERVER_ERROR",
        }

    def test_generic_exception_hides_message_and_attributes(self) -> None:
        assert default_error_envelope(RuntimeError("private"), 500, "id") == {
            "message": "Internal server error",
            "code": "INTERNAL_SERVER_ERROR",
        }

    def test_authentication_error_excludes_response_body_and_details(self) -> None:
        error = AuthenticationError(status_code=401, response_body=b"private")
        payload = default_error_envelope(error, 502, None)
        assert payload == {
            "message": "Authentication failed with status 401",
            "code": "AUTHENTICATION_ERROR",
        }

    def test_explicit_details_preserves_existing_opt_in_payload(self) -> None:
        payload = default_error_envelope(
            InvalidInputError(details={"field": "name"}),
            400,
            None,
            include_details=True,
        )
        assert payload["details"] == {"field": "name"}

    def test_details_are_omitted_when_absent_even_if_enabled(self) -> None:
        assert "details" not in default_error_envelope(
            BaseError("custom"), 500, None, include_details=True
        )


class TestBuildErrorEnvelope:
    def test_no_custom_callable_uses_default_without_logging(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        error = InvalidInputError()
        assert build_error_envelope(error, 400, None) == default_error_envelope(
            error, 400, None
        )
        assert caplog.records == []

    def test_callable_receives_exact_error_status_and_request_id(self) -> None:
        error = InvalidInputError()

        def custom(
            exc: Exception, status: int, request_id: str | None
        ) -> Mapping[str, object]:
            assert exc is error
            assert status == 400
            assert request_id == "scoped-id"
            return {
                "error": {"code": "CUSTOM", "status": status},
                "request_id": request_id,
                "values": [True, None, 1, 1.5],
            }

        assert build_error_envelope(error, 400, "scoped-id", envelope=custom) == {
            "error": {"code": "CUSTOM", "status": 400},
            "request_id": "scoped-id",
            "values": [True, None, 1, 1.5],
        }

    def test_mapping_result_is_copied_to_plain_dict(self) -> None:
        source: dict[str, object] = {"code": "CUSTOM"}
        result = build_error_envelope(
            BaseError("custom"),
            500,
            None,
            envelope=lambda *_: MappingProxyType(source),
        )
        assert type(result) is dict
        assert result == source
        assert result is not source

    def test_custom_payload_owns_details_and_accepts_missing_request_id(self) -> None:
        def custom(
            exc: Exception, status: int, request_id: str | None
        ) -> Mapping[str, object]:
            assert request_id is None
            return {}

        assert (
            build_error_envelope(
                InvalidInputError(details={"private": "value"}),
                400,
                None,
                envelope=custom,
                include_details=True,
            )
            == {}
        )

    def test_callback_failure_logs_safe_message_and_returns_default(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        def failing(
            exc: Exception, status: int, request_id: str | None
        ) -> Mapping[str, object]:
            raise RuntimeError("private-callback-message")

        error = InvalidInputError(details={"private": "value"})
        assert build_error_envelope(
            error, 400, "request-123", envelope=failing
        ) == default_error_envelope(error, 400, "request-123")
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.name == "plynt.base.error_envelope"
        assert record.levelname == "ERROR"
        assert record.getMessage() == (
            "Custom error envelope failed; using default error payload"
        )
        assert record.exc_info is None
        assert "private" not in caplog.text

    @pytest.mark.parametrize(
        "invalid",
        [
            None,
            [],
            {"bad": object()},
            {"bad": b"private"},
            {"bad": float("nan")},
            {1: "bad"},
        ],
    )
    def test_invalid_output_logs_failure_and_falls_back(
        self, invalid: object, caplog: pytest.LogCaptureFixture
    ) -> None:
        callback = cast(ErrorEnvelope, lambda *_: invalid)
        error = InvalidInputError()
        assert build_error_envelope(
            error, 400, None, envelope=callback
        ) == default_error_envelope(error, 400, None)
        assert len(caplog.records) == 1

    def test_circular_output_falls_back(self, caplog: pytest.LogCaptureFixture) -> None:
        circular: dict[str, object] = {}
        circular["self"] = circular
        error = InvalidInputError()
        assert build_error_envelope(
            error, 400, None, envelope=lambda *_: circular
        ) == default_error_envelope(error, 400, None)
        assert len(caplog.records) == 1

    def test_fallback_retains_explicit_details_option(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        def failing(
            exc: Exception, status: int, request_id: str | None
        ) -> Mapping[str, object]:
            raise ValueError("failure")

        payload = build_error_envelope(
            InvalidInputError(details={"field": "name"}),
            400,
            None,
            envelope=failing,
            include_details=True,
        )
        assert payload["details"] == {"field": "name"}
        assert len(caplog.records) == 1

    def test_process_control_exception_propagates_without_fallback(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        def interrupted(
            exc: Exception, status: int, request_id: str | None
        ) -> Mapping[str, object]:
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            build_error_envelope(InvalidInputError(), 400, None, envelope=interrupted)
        assert caplog.records == []
