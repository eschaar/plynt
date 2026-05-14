"""Tests for plynth.http.request (Request)."""

from plynth.base.request import Request


class TestRequest:
    """Test suite for Request."""

    def test_minimal(self) -> None:
        """Validate minimal."""
        req = Request(method="GET", url="https://example.com")
        assert req.method == "GET"
        assert req.url == "https://example.com"
        assert req.headers == {}
        assert req.params == {}
        assert req.content is None

    def test_with_headers_and_body(self) -> None:
        """Validate with headers and body."""
        req = Request(
            method="POST",
            url="https://example.com/api",
            headers={"Content-Type": "application/json"},
            content=b'{"key": "value"}',
        )
        assert req.headers["Content-Type"] == "application/json"
        assert req.content == b'{"key": "value"}'

    def test_with_params(self) -> None:
        """Validate with params."""
        req = Request(
            method="GET",
            url="https://example.com/search",
            params={"q": "plynth", "page": 1},
        )
        assert req.params["q"] == "plynth"
        assert req.params["page"] == 1

    def test_timeout_defaults_to_none(self) -> None:
        """Validate timeout defaults to none."""
        req = Request(method="GET", url="https://example.com")
        assert req.timeout is None

    def test_timeout_can_be_set(self) -> None:
        """Validate timeout can be set."""
        req = Request(method="GET", url="https://example.com", timeout=120.0)
        assert req.timeout == 120.0

    def test_stream_defaults_to_false(self) -> None:
        """Validate stream defaults to false."""
        req = Request(method="GET", url="https://example.com")
        assert req.stream is False

    def test_stream_can_be_enabled(self) -> None:
        """Validate stream can be enabled."""
        req = Request(method="GET", url="https://example.com", stream=True)
        assert req.stream is True
