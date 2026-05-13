import pytest

from plynth.base.errors import (
    BaseError,
    DependencyUnavailableError,
    FeatureDisabledError,
    InvalidInputError,
    StatusError,
    TransportError,
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
