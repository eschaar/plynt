"""Tests for plynt.base.response (Response, ResponseProtocol)
and plynt.http.response (HttpResponse)."""

from collections.abc import AsyncIterator, Iterator

import pytest

from plynt.base.errors import StatusError, StreamInterruptedError
from plynt.base.response import (
    AsyncStreamingResponse,
    Response,
    ResponseProtocol,
    StreamingResponse,
)
from plynt.http.errors import HttpStatusError
from plynt.http.response import HttpResponse


class _SyncRaw:
    """Small sync raw response double for streaming response tests."""

    def __init__(self) -> None:
        """Initialize the raw response test double."""
        self.closed = False
        self.last_chunk_size: int | None = None

    def close(self) -> None:
        """Mark raw response as closed."""
        self.closed = True

    def iter_lines(self) -> Iterator[str]:
        """Return text lines."""
        return iter(("a", "b"))

    def iter_bytes(self, chunk_size: int | None = None) -> Iterator[bytes]:
        """Return byte chunks and capture optional chunk size."""
        self.last_chunk_size = chunk_size
        return iter((b"a", b"b"))


class _SyncFailingRaw(_SyncRaw):
    """Sync raw response double that fails during iteration."""

    def iter_lines(self) -> Iterator[str]:
        """Raise mid-iteration while yielding text lines."""

        def _lines() -> Iterator[str]:
            yield "a"
            raise RuntimeError("stream failed")

        return _lines()

    def iter_bytes(self, chunk_size: int | None = None) -> Iterator[bytes]:
        """Raise mid-iteration while yielding byte chunks."""
        self.last_chunk_size = chunk_size

        def _bytes() -> Iterator[bytes]:
            yield b"a"
            raise RuntimeError("stream failed")

        return _bytes()


class _AsyncRaw:
    """Small async raw response double for streaming response tests."""

    def __init__(self) -> None:
        """Initialize the async raw response test double."""
        self.closed = False
        self.last_chunk_size: int | None = None

    async def aclose(self) -> None:
        """Mark raw response as closed."""
        self.closed = True

    async def _lines(self) -> AsyncIterator[str]:
        """Yield text lines."""
        yield "a"
        yield "b"

    async def _bytes(self) -> AsyncIterator[bytes]:
        """Yield byte chunks."""
        yield b"a"
        yield b"b"

    def aiter_lines(self) -> AsyncIterator[str]:
        """Return an async iterator of lines."""
        return self._lines()

    def aiter_bytes(self, chunk_size: int | None = None) -> AsyncIterator[bytes]:
        """Return an async iterator of bytes and capture chunk size."""
        self.last_chunk_size = chunk_size
        return self._bytes()


class _AsyncFailingRaw(_AsyncRaw):
    """Async raw response double that fails during iteration."""

    async def _lines(self) -> AsyncIterator[str]:
        """Raise mid-iteration while yielding text lines."""
        yield "a"
        raise RuntimeError("stream failed")

    async def _bytes(self) -> AsyncIterator[bytes]:
        """Raise mid-iteration while yielding byte chunks."""
        yield b"a"
        raise RuntimeError("stream failed")


class TestResponse:
    """Test suite for Response."""

    def test_minimal(self) -> None:
        """Validate minimal."""
        resp = Response(status_code=200)
        assert resp.status_code == 200
        assert not resp.headers
        assert resp.content == b""
        assert vars(resp).get("_raw") is None

    def test_raw_stores_arbitrary_object(self) -> None:
        """Validate raw stores arbitrary object."""
        raw = object()
        resp = Response(status_code=200, _raw=raw)
        assert vars(resp).get("_raw") is raw

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
                raise NotImplementedError

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
        assert vars(resp).get("_raw") is None

    def test_raw_stores_arbitrary_object(self) -> None:
        """Validate raw stores arbitrary object."""
        raw = object()
        resp = HttpResponse(status_code=200, method="GET", url="/", _raw=raw)
        assert vars(resp).get("_raw") is raw

    def test_raw_excluded_from_equality(self) -> None:
        """Validate raw excluded from equality."""
        sentinel = object()
        resp_a = HttpResponse(status_code=200, method="GET", url="/")
        resp_b = HttpResponse(status_code=200, method="GET", url="/", _raw=sentinel)
        assert resp_a == resp_b


class TestStreamingResponse:
    """Test suite for StreamingResponse."""

    def test_enter_returns_self(self) -> None:
        """Validate context enter returns self."""
        resp = StreamingResponse(status_code=200)
        with resp as entered:
            assert entered is resp

    def test_exit_with_raw_closes_raw(self) -> None:
        """Validate exit closes underlying raw response."""
        raw = _SyncRaw()
        resp = StreamingResponse(status_code=200, _raw=raw)
        resp.__exit__(None, None, None)
        assert raw.closed

    def test_exit_without_raw_is_noop(self) -> None:
        """Validate exit without raw does not raise."""
        StreamingResponse(status_code=200).__exit__(None, None, None)

    def test_iter_lines_delegates_to_raw(self) -> None:
        """Validate iter_lines delegates to raw response."""
        raw = _SyncRaw()
        resp = StreamingResponse(status_code=200, _raw=raw)
        assert list(resp.iter_lines()) == ["a", "b"]

    def test_iter_bytes_delegates_without_chunk_size(self) -> None:
        """Validate iter_bytes delegates without chunk size."""
        raw = _SyncRaw()
        resp = StreamingResponse(status_code=200, _raw=raw)
        assert list(resp.iter_bytes()) == [b"a", b"b"]
        assert raw.last_chunk_size is None

    def test_iter_bytes_delegates_with_chunk_size(self) -> None:
        """Validate iter_bytes forwards explicit chunk size."""
        raw = _SyncRaw()
        resp = StreamingResponse(status_code=200, _raw=raw)
        assert list(resp.iter_bytes(chunk_size=4)) == [b"a", b"b"]
        assert raw.last_chunk_size == 4

    def test_iter_lines_maps_interruption_to_stream_interrupted_error(self) -> None:
        """Validate iter_lines maps raw iteration failures to StreamInterruptedError."""
        raw = _SyncFailingRaw()
        resp = StreamingResponse(status_code=200, _raw=raw)

        with pytest.raises(StreamInterruptedError) as exc_info:
            list(resp.iter_lines())

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert exc_info.value.details is not None
        assert exc_info.value.details["underlying_error"] is exc_info.value.__cause__

    def test_iter_bytes_maps_interruption_to_stream_interrupted_error(self) -> None:
        """Validate iter_bytes maps raw iteration failures to StreamInterruptedError."""
        raw = _SyncFailingRaw()
        resp = StreamingResponse(status_code=200, _raw=raw)

        with pytest.raises(StreamInterruptedError) as exc_info:
            list(resp.iter_bytes())

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert exc_info.value.details is not None
        assert exc_info.value.details["underlying_error"] is exc_info.value.__cause__

    def test_close_with_raw_closes_raw(self) -> None:
        """Validate close closes underlying raw response."""
        raw = _SyncRaw()
        resp = StreamingResponse(status_code=200, _raw=raw)
        resp.close()
        assert raw.closed

    def test_close_without_raw_raises_clear_runtime_error(self) -> None:
        """Validate close without raw raises a clear RuntimeError."""
        with pytest.raises(RuntimeError, match="has no bound raw stream"):
            StreamingResponse(status_code=200).close()

    def test_iter_lines_without_raw_raises_clear_runtime_error(self) -> None:
        """Validate iter_lines without raw raises a clear RuntimeError."""
        resp = StreamingResponse(status_code=200)

        with pytest.raises(RuntimeError, match="has no bound raw stream"):
            list(resp.iter_lines())

    def test_iter_bytes_without_raw_raises_clear_runtime_error(self) -> None:
        """Validate iter_bytes without raw raises a clear RuntimeError."""
        resp = StreamingResponse(status_code=200)

        with pytest.raises(RuntimeError, match="has no bound raw stream"):
            list(resp.iter_bytes())


class TestAsyncStreamingResponse:
    """Test suite for AsyncStreamingResponse."""

    @pytest.mark.anyio
    async def test_aenter_returns_self(self) -> None:
        """Validate async context enter returns self."""
        resp = AsyncStreamingResponse(status_code=200)
        async with resp as entered:
            assert entered is resp

    @pytest.mark.anyio
    async def test_aexit_with_raw_closes_raw(self) -> None:
        """Validate async exit closes underlying raw response."""
        raw = _AsyncRaw()
        resp = AsyncStreamingResponse(status_code=200, _raw=raw)
        await resp.__aexit__(None, None, None)
        assert raw.closed

    @pytest.mark.anyio
    async def test_aexit_without_raw_is_noop(self) -> None:
        """Validate async exit without raw does not raise."""
        await AsyncStreamingResponse(status_code=200).__aexit__(None, None, None)

    @pytest.mark.anyio
    async def test_aiter_lines_delegates_to_raw(self) -> None:
        """Validate aiter_lines delegates to raw response."""
        raw = _AsyncRaw()
        resp = AsyncStreamingResponse(status_code=200, _raw=raw)
        collected = [line async for line in resp.aiter_lines()]
        assert collected == ["a", "b"]

    @pytest.mark.anyio
    async def test_aiter_bytes_without_chunk_size(self) -> None:
        """Validate aiter_bytes delegates without chunk size."""
        raw = _AsyncRaw()
        resp = AsyncStreamingResponse(status_code=200, _raw=raw)
        collected = [chunk async for chunk in resp.aiter_bytes()]
        assert collected == [b"a", b"b"]
        assert raw.last_chunk_size is None

    @pytest.mark.anyio
    async def test_aiter_bytes_with_chunk_size(self) -> None:
        """Validate aiter_bytes forwards explicit chunk size."""
        raw = _AsyncRaw()
        resp = AsyncStreamingResponse(status_code=200, _raw=raw)
        collected = [chunk async for chunk in resp.aiter_bytes(chunk_size=8)]
        assert collected == [b"a", b"b"]
        assert raw.last_chunk_size == 8

    @pytest.mark.anyio
    async def test_aiter_lines_maps_interruption_to_stream_interrupted_error(
        self,
    ) -> None:
        """Validate aiter_lines maps raw iteration failures.

        Iteration failures must raise StreamInterruptedError.
        """
        raw = _AsyncFailingRaw()
        resp = AsyncStreamingResponse(status_code=200, _raw=raw)

        async def _consume_lines() -> None:
            consumed: list[str] = []
            async for _line in resp.aiter_lines():
                consumed.append(_line)

        with pytest.raises(StreamInterruptedError) as exc_info:
            await _consume_lines()

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert exc_info.value.details is not None
        assert exc_info.value.details["underlying_error"] is exc_info.value.__cause__

    @pytest.mark.anyio
    async def test_aiter_bytes_maps_interruption_to_stream_interrupted_error(
        self,
    ) -> None:
        """Validate aiter_bytes maps raw iteration failures.

        Iteration failures must raise StreamInterruptedError.
        """
        raw = _AsyncFailingRaw()
        resp = AsyncStreamingResponse(status_code=200, _raw=raw)

        async def _consume_bytes() -> None:
            consumed: list[bytes] = []
            async for _chunk in resp.aiter_bytes():
                consumed.append(_chunk)

        with pytest.raises(StreamInterruptedError) as exc_info:
            await _consume_bytes()

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert exc_info.value.details is not None
        assert exc_info.value.details["underlying_error"] is exc_info.value.__cause__

    @pytest.mark.anyio
    async def test_aclose_with_raw_closes_raw(self) -> None:
        """Validate aclose closes underlying raw response."""
        raw = _AsyncRaw()
        resp = AsyncStreamingResponse(status_code=200, _raw=raw)
        await resp.aclose()
        assert raw.closed

    @pytest.mark.anyio
    async def test_aclose_without_raw_raises_clear_runtime_error(self) -> None:
        """Validate aclose without raw raises a clear RuntimeError."""
        with pytest.raises(RuntimeError, match="has no bound raw stream"):
            await AsyncStreamingResponse(status_code=200).aclose()

    @pytest.mark.anyio
    async def test_aiter_lines_without_raw_raises_clear_runtime_error(self) -> None:
        """Validate aiter_lines without raw raises a clear RuntimeError."""
        resp = AsyncStreamingResponse(status_code=200)

        async def _consume_lines() -> None:
            async for _line in resp.aiter_lines():
                pass

        with pytest.raises(RuntimeError, match="has no bound raw stream"):
            await _consume_lines()

    @pytest.mark.anyio
    async def test_aiter_bytes_without_raw_raises_clear_runtime_error(self) -> None:
        """Validate aiter_bytes without raw raises a clear RuntimeError."""
        resp = AsyncStreamingResponse(status_code=200)

        async def _consume_bytes() -> None:
            async for _chunk in resp.aiter_bytes():
                pass

        with pytest.raises(RuntimeError, match="has no bound raw stream"):
            await _consume_bytes()
