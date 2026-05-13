"""Tests for plynth.base.response (Response, ResponseProtocol)
and plynth.http.response (HttpResponse)."""

import pytest

from plynth.base.errors import StatusError
from plynth.base.response import Response, ResponseProtocol
from plynth.http.errors import HttpStatusError
from plynth.http.response import HttpResponse


class TestResponse:
    """Test suite for Response."""

    def test_minimal(self) -> None:
        """Validate minimal."""
        resp = Response(status_code=200)
        assert resp.status_code == 200
        assert resp.headers == {}
        assert resp.content == b""
        assert resp._raw is None

    def test_raw_stores_arbitrary_object(self) -> None:
        """Validate raw stores arbitrary object."""
        raw = object()
        resp = Response(status_code=200, _raw=raw)
        assert resp._raw is raw

    def test_raw_excluded_from_equality(self) -> None:
        """Validate raw excluded from equality."""
        sentinel = object()
        resp_a = Response(status_code=200)
        resp_b = Response(status_code=200, _raw=sentinel)
        assert resp_a == resp_b

    def test_raw_excluded_from_repr(self) -> None:
        """Validate raw excluded from repr."""
        raw = object()
        resp = Response(status_code=200, _raw=raw)
        assert "_raw" not in repr(resp)

    def test_with_headers_and_content(self) -> None:
        """Validate with headers and content."""
        resp = Response(
            status_code=201,
            headers={"Location": "/api/items/1"},
            content=b"created",
        )
        assert resp.status_code == 201
        assert resp.headers["Location"] == "/api/items/1"
        assert resp.content == b"created"

    def test_raise_for_status_success(self) -> None:
        """Validate raise for status success."""
        resp = Response(status_code=200)
        resp.raise_for_status()  # must not raise

    def test_raise_for_status_client_error(self) -> None:
        """Validate raise for status client error."""
        resp = Response(status_code=404)
        with pytest.raises(StatusError) as exc_info:
            resp.raise_for_status()
        assert exc_info.value.status_code == 404

    def test_raise_for_status_server_error(self) -> None:
        """Validate raise for status server error."""
        resp = Response(status_code=500)
        with pytest.raises(StatusError) as exc_info:
            resp.raise_for_status()
        assert exc_info.value.status_code == 500


class TestResponseProtocol:
    """Test suite for ResponseProtocol."""

    def test_response_satisfies_protocol(self) -> None:
        """Validate response satisfies protocol."""
        resp = Response(status_code=200)
        assert isinstance(resp, ResponseProtocol)

    def test_arbitrary_object_satisfies_protocol(self) -> None:
        """Any object with the right shape satisfies ResponseProtocol."""

        class FakeResponse:
            """Represent FakeResponse."""

            def __init__(self) -> None:
                """Initialize FakeResponse."""
                self.status_code = 200
                self.headers = {"content-type": "application/json"}
                self.content = b"{}"

            def raise_for_status(self) -> None:
                """Return raise for status."""
                pass

        assert isinstance(FakeResponse(), ResponseProtocol)

    def test_incomplete_object_does_not_satisfy_protocol(self) -> None:
        """An object missing required attributes does not satisfy the protocol."""

        class Incomplete:
            """Represent Incomplete."""

            status_code = 200
            # missing: headers, content, raise_for_status

        assert not isinstance(Incomplete(), ResponseProtocol)


class TestHttpResponse:
    """Test suite for HttpResponse."""

    def test_is_response(self) -> None:
        """Validate is response."""
        resp = HttpResponse(status_code=200, method="GET", url="https://example.com")
        assert isinstance(resp, Response)

    def test_satisfies_protocol(self) -> None:
        """Validate satisfies protocol."""
        resp = HttpResponse(status_code=200, method="GET", url="https://example.com")
        assert isinstance(resp, ResponseProtocol)

    def test_raise_for_status_success(self) -> None:
        """Validate raise for status success."""
        resp = HttpResponse(status_code=200, method="GET", url="https://example.com")
        resp.raise_for_status()  # must not raise

    def test_raise_for_status_raises_http_status_error(self) -> None:
        """Validate raise for status raises http status error."""
        resp = HttpResponse(
            status_code=404,
            method="GET",
            url="https://api.example.com/items/1",
        )
        with pytest.raises(HttpStatusError) as exc_info:
            resp.raise_for_status()
        err = exc_info.value
        assert err.status_code == 404
        assert err.method == "GET"
        assert err.url == "https://api.example.com/items/1"

    def test_http_status_error_is_status_error(self) -> None:
        """HttpStatusError is catchable as StatusError for generic handling."""
        resp = HttpResponse(status_code=500, method="POST", url="/jobs")
        with pytest.raises(StatusError):
            resp.raise_for_status()

    def test_raw_defaults_to_none(self) -> None:
        """Validate raw defaults to none."""
        resp = HttpResponse(status_code=200, method="GET", url="/")
        assert resp._raw is None

    def test_raw_stores_arbitrary_object(self) -> None:
        """Validate raw stores arbitrary object."""
        raw = object()
        resp = HttpResponse(status_code=200, method="GET", url="/", _raw=raw)
        assert resp._raw is raw

    def test_raw_excluded_from_equality(self) -> None:
        """Validate raw excluded from equality."""
        sentinel = object()
        resp_a = HttpResponse(status_code=200, method="GET", url="/")
        resp_b = HttpResponse(status_code=200, method="GET", url="/", _raw=sentinel)
        assert resp_a == resp_b
