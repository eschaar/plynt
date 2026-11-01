import pytest

from plynt.base.errors import (
    AuthenticationError,
    BaseError,
    DependencyUnavailableError,
    FeatureDisabledError,
    InvalidInputError,
    StatusError,
    TransportConnectionError,
    TransportError,
    TransportTimeoutError,
)


class TestCoreErrors:
    """Test suite for CoreErrors."""

    def test_base_error(self) -> None:
        """Test that BaseError can be instantiated and its attributes are correct."""
        err = BaseError(message="msg", code="CODE", details={"foo": "bar"})
        assert err.message == "msg"
        assert err.code == "CODE"
        assert err.details == {"foo": "bar"}
        assert isinstance(err.to_dict(), dict)
        assert BaseError.from_dict(err.to_dict()).message == "msg"

    def test_invalid_input(self) -> None:
        """Test that InvalidInputError is a subclass of BaseError."""
        err = InvalidInputError(message="bad input", code="INVALID")
        assert isinstance(err, BaseError)
        assert err.message == "bad input"
        assert err.code == "INVALID"

    def test_feature_disabled(self) -> None:
        """Test that FeatureDisabledError is a subclass of BaseError."""
        err = FeatureDisabledError(message="disabled")
        assert err.message == "disabled"
        assert isinstance(err, BaseError)

    def test_dependency_unavailable(self) -> None:
        """Test that DependencyUnavailableError is a subclass of BaseError."""
        err = DependencyUnavailableError(message="dep fail")
        assert err.message == "dep fail"
        assert isinstance(err, BaseError)

    def test_base_error_str_and_repr(self) -> None:
        """Test that __str__ and __repr__ include class name and message."""
        err = BaseError(message="foo", code="BAR", details={"x": 1})
        s = str(err)
        r = repr(err)
        assert "BaseError" in s
        assert "foo" in s
        assert "BaseError" in r
        assert "foo" in r
        assert "BAR" in r
        assert "x" in r

    def test_base_error_str_only_class_name(self) -> None:
        """Test that __str__ returns only class name if message is None."""

        class NoMessageError(BaseError):
            """Represent NoMessageError."""

            pass

        err = NoMessageError(message="fallback")
        err.message = None
        assert str(err) == "NoMessageError"

    def test_missing_message_raises_value_error(self) -> None:
        """Instantiating BaseError without a message or class default
        raises ValueError."""

        class NoDefaultError(BaseError):
            """Represent NoDefaultError."""

            pass

        with pytest.raises(ValueError, match="requires a non-empty message"):
            NoDefaultError()


class TestTransportError:
    """Test suite for TransportError."""

    def test_is_base_error(self) -> None:
        """Validate is base error."""
        err = TransportError()
        assert isinstance(err, BaseError)

    def test_default_message_and_code(self) -> None:
        """Validate default message and code."""
        err = TransportError()
        assert err.code == "TRANSPORT_ERROR"
        assert "transport" in err.message.lower()

    def test_custom_message(self) -> None:
        """Validate custom message."""
        err = TransportError("Connection refused")
        assert err.message == "Connection refused"


@pytest.mark.parametrize(
    ("error_type", "code", "message"),
    [
        (
            TransportTimeoutError,
            "TRANSPORT_TIMEOUT",
            "The transport operation timed out",
        ),
        (
            TransportConnectionError,
            "TRANSPORT_CONNECTION_ERROR",
            "The transport connection failed",
        ),
    ],
)
class TestTypedTransportErrors:
    def test_default_contract(
        self, error_type: type[TransportError], code: str, message: str
    ) -> None:
        error = error_type()

        assert isinstance(error, BaseError)
        assert isinstance(error, TransportError)
        assert not isinstance(error, StatusError)
        assert error.message == message
        assert error.code == code
        assert error.to_dict() == {"message": message, "code": code}

    def test_custom_contract_round_trip(
        self, error_type: type[TransportError], code: str, message: str
    ) -> None:
        error = error_type(
            "Custom failure", code="CUSTOM", details={"operation": "send"}
        )
        restored = error_type.from_dict(error.to_dict())

        assert type(restored) is error_type
        assert restored.to_dict() == {
            "message": "Custom failure",
            "code": "CUSTOM",
            "details": {"operation": "send"},
        }
        assert error_type.__name__ in str(restored)
        assert "Custom failure" in str(restored)
        assert restored.code != code
        assert restored.message != message

    def test_explicit_cause_is_preserved(
        self, error_type: type[TransportError], code: str, message: str
    ) -> None:
        cause = OSError("Network failure")

        with pytest.raises(TransportError) as caught:
            raise error_type() from cause

        assert type(caught.value) is error_type
        assert caught.value.__cause__ is cause
        assert caught.value.code == code
        assert caught.value.message == message


class TestAuthenticationError:
    @pytest.mark.parametrize("status_code", [400, 401, 403, 500])
    def test_status_code_has_safe_structured_representation(
        self, status_code: int
    ) -> None:
        error = AuthenticationError(status_code=status_code)

        assert isinstance(error, BaseError)
        assert isinstance(error, TransportError)
        assert isinstance(error, RuntimeError)
        assert not isinstance(error, StatusError)
        assert error.status_code == status_code
        assert error.response_body is None
        assert error.to_dict() == {
            "message": f"Authentication failed with status {status_code}",
            "code": "AUTHENTICATION_ERROR",
            "details": {"status_code": status_code},
        }

    @pytest.mark.parametrize("body", [b"", b"Upstream diagnostic text", b"\xff\x00"])
    def test_response_body_is_available_but_excluded_from_output(
        self, body: bytes
    ) -> None:
        error = AuthenticationError(status_code=401, response_body=body)
        without_body = AuthenticationError(status_code=401)

        assert error.response_body == body
        assert error.message == without_body.message
        assert error.args == without_body.args
        assert str(error) == str(without_body)
        assert repr(error) == repr(without_body)
        assert error.to_dict() == without_body.to_dict()

    @pytest.mark.parametrize("status_code", [400, 401, 403, 500])
    def test_from_dict_round_trip_restores_status_without_response_body(
        self, status_code: int
    ) -> None:
        error = AuthenticationError(status_code=status_code, response_body=b"private")

        restored = AuthenticationError.from_dict(error.to_dict())

        assert type(restored) is AuthenticationError
        assert restored.status_code == status_code
        assert restored.response_body is None
        assert restored.to_dict() == error.to_dict()
        assert b"private" not in repr(restored).encode()

    @pytest.mark.parametrize(
        "payload",
        [
            {"message": "Authentication failed"},
            {"details": {}},
            {"details": {"status_code": True}},
            {"details": {"status_code": "401"}},
        ],
    )
    def test_from_dict_requires_integer_status_detail(
        self, payload: dict[str, object]
    ) -> None:
        with pytest.raises(
            ValueError,
            match="AuthenticationError details must include an integer status_code",
        ):
            AuthenticationError.from_dict(payload)

    def test_existing_runtime_error_handler_catches_authentication_error(self) -> None:
        error = AuthenticationError(status_code=401)

        with pytest.raises(RuntimeError) as caught:
            raise error

        assert caught.value is error

    def test_status_code_is_required(self) -> None:
        with pytest.raises(TypeError):
            AuthenticationError()  # type: ignore[call-arg]


class TestStatusError:
    """Test suite for StatusError."""

    def test_is_transport_error(self) -> None:
        """Validate is transport error."""
        err = StatusError(status_code=404)
        assert isinstance(err, TransportError)

    def test_status_code_stored(self) -> None:
        """Validate status code stored."""
        err = StatusError(status_code=404)
        assert err.status_code == 404

    def test_status_code_in_details(self) -> None:
        """Validate status code in details."""
        err = StatusError(status_code=500)
        assert err.details is not None
        assert err.details["status_code"] == 500

    def test_default_code(self) -> None:
        """Validate default code."""
        err = StatusError(status_code=422)
        assert err.code == "STATUS_ERROR"

    def test_custom_message(self) -> None:
        """Validate custom message."""
        err = StatusError("Account not found", status_code=404)
        assert err.message == "Account not found"
        assert err.status_code == 404

    def test_to_dict(self) -> None:
        """Validate to dict."""
        err = StatusError(status_code=503)
        d = err.to_dict()
        assert d["message"] == err.message
        assert d["code"] == "STATUS_ERROR"
        assert d["details"]["status_code"] == 503

    def test_status_code_required(self) -> None:
        """Validate status code required."""
        with pytest.raises(TypeError):
            StatusError()  # type: ignore[call-arg]
