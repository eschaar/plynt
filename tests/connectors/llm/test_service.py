"""Tests for LLMService and AsyncLLMService."""

from __future__ import annotations

import inspect
import json
from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from plynt.base.response import AsyncStreamingResponse, StreamingResponse
from plynt.connectors.llm import (
    AsyncLLMService,
    LLMGenerateRequest,
    LLMService,
    LLMStreamChunk,
    LLMStreamParseError,
)
from plynt.connectors.llm.adapters import LLMAdapterSet, build_default_adapter_set
from plynt.http.client import APIClient, AsyncAPIClient
from plynt.http.renderer import JSONRenderer
from tests.conftest import MockAsyncTransport, MockSyncTransport

_JSON_RENDERER = JSONRenderer()
_DUMMY_BASE_URL = "https://llm.example.com"


class _SyncLineRaw:
    """Simple raw stream stub with iter_lines()."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def iter_lines(self) -> Iterator[str]:
        return iter(self._lines)


class _SyncBytesLineRaw:
    """Simple raw stream stub with iter_lines() yielding bytes."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def iter_lines(self) -> Iterator[bytes]:
        return iter(self._lines)


class _AsyncLineRaw:
    """Simple raw stream stub with aiter_lines()."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line


def _json_bytes(data: Any) -> bytes:
    """Render arbitrary payload to JSON bytes."""
    return _JSON_RENDERER.render(data)


def _make_service(
    *,
    status_code: int = 200,
    content: bytes = b"{}",
    adapter_set: LLMAdapterSet | None = None,
) -> tuple[LLMService, MockSyncTransport]:
    """Build LLMService with a sync mock transport."""
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = APIClient(base_url=_DUMMY_BASE_URL, transport=transport)
    return LLMService(client, adapter_set=adapter_set), transport


def _make_async_service(
    *,
    status_code: int = 200,
    content: bytes = b"{}",
    adapter_set: LLMAdapterSet | None = None,
) -> tuple[AsyncLLMService, MockAsyncTransport]:
    """Build AsyncLLMService with an async mock transport."""
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncAPIClient(base_url=_DUMMY_BASE_URL, transport=transport)
    return AsyncLLMService(client, adapter_set=adapter_set), transport


class _TestRequestAdapter:
    """Test request adapter that records invocation metadata."""

    def __init__(self) -> None:
        self.calls: list[tuple[bool, str | None]] = []

    def to_provider_payload(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        self.calls.append((stream, request.model))
        return {
            "input": request.to_payload()["messages"],
            "streaming": stream,
        }


class _TestResponseAdapter:
    """Test response adapter mapping provider payload to neutral completion shape."""

    def to_neutral_completion_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = payload.get("text", "")
        if not isinstance(text, str):
            text = ""

        return {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ]
        }


class _TestStreamAdapter:
    """Test stream adapter that records payload lines passed for parsing."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def parse_event_payload(self, payload_line: str) -> LLMStreamChunk | None:
        self.calls.append(payload_line)
        return LLMService.parse_stream_line(
            payload_line,
            adapter_set=build_default_adapter_set(),
        )


class TestLLMService:
    """Tests for LLMService."""

    def test_generate_posts_expected_payload_and_parses_completion(self) -> None:
        """generate sends normalized payload and parses generic completion."""
        payload = {
            "id": "cmp-1",
            "model": "demo",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hi"},
                    "finish_reason": "stop",
                }
            ],
        }
        svc, transport = _make_service(content=_json_bytes(payload))
        request = LLMGenerateRequest(messages=[{"role": "user", "content": "Hello"}])

        result = svc.generate(request)

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith("/v1/llm/chat/completions")
        assert json.loads(sent.content or b"{}") == {
            "messages": [{"role": "user", "content": "Hello"}],
        }
        assert result.choices[0].message.content == "Hi"

    def test_generate_stream_uses_stream_request(self) -> None:
        """generate_stream enables stream mode and returns StreamingResponse."""
        svc, transport = _make_service()
        streaming = StreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=MagicMock(),
        )
        transport.send.return_value = streaming

        request = LLMGenerateRequest(messages=[{"role": "user", "content": "Hello"}])
        result = svc.generate_stream(request)

        sent = transport.send.call_args[0][0]
        assert sent.stream is True
        assert json.loads(sent.content or b"{}") == {
            "messages": [{"role": "user", "content": "Hello"}],
            "options": {"stream": True},
        }
        assert isinstance(result, StreamingResponse)

    def test_generate_uses_request_and_response_adapters(self) -> None:
        """generate uses adapter set for provider request and response mapping."""
        request_adapter = _TestRequestAdapter()
        response_adapter = _TestResponseAdapter()

        payload = {"text": "ok"}
        svc, transport = _make_service(
            content=_json_bytes(payload),
            adapter_set=LLMAdapterSet(
                request_adapter=request_adapter,
                completion_adapter=response_adapter,
                stream_adapter=build_default_adapter_set().stream_adapter,
            ),
        )

        request = LLMGenerateRequest(
            messages=[{"role": "user", "content": "Hello"}],
            model="demo",
        )
        result = svc.generate(request)

        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content or b"{}") == {
            "input": [{"role": "user", "content": "Hello"}],
            "streaming": False,
        }
        assert request_adapter.calls == [(False, "demo")]
        assert result.choices[0].message.content == "ok"

    def test_generate_supports_deprecated_payload_adapter_alias(self) -> None:
        """generate supports legacy payload_adapter constructor argument."""

        def payload_adapter(request: LLMGenerateRequest) -> dict[str, Any]:
            return {
                "legacy_input": request.to_payload()["messages"],
                "legacy_stream": False,
            }

        payload = {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ]
        }
        transport = MockSyncTransport(content=_json_bytes(payload))
        client = APIClient(base_url=_DUMMY_BASE_URL, transport=transport)
        with pytest.warns(DeprecationWarning, match="payload_adapter is deprecated"):
            svc = LLMService(client, payload_adapter=payload_adapter)

        request = LLMGenerateRequest(messages=[{"role": "user", "content": "Hi"}])
        result = svc.generate(request)

        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content or b"{}") == {
            "legacy_input": [{"role": "user", "content": "Hi"}],
            "legacy_stream": False,
        }
        assert result.choices[0].message.content == "ok"

    def test_constructor_rejects_adapter_set_and_payload_adapter_together(
        self,
    ) -> None:
        """LLMService rejects mutually exclusive adapter constructor options."""
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=_DUMMY_BASE_URL, transport=transport)

        with pytest.raises(ValueError):
            LLMService(
                client,
                adapter_set=build_default_adapter_set(),
                payload_adapter=lambda request: request.to_payload(),
            )

    def test_generate_falls_back_for_non_object_completion_payload(self) -> None:
        """Generate normalizes non-object JSON responses to an empty payload."""
        svc, _ = _make_service(content=_json_bytes(["unexpected"]))
        request = LLMGenerateRequest(messages=[{"role": "user", "content": "Hi"}])

        result = svc.generate(request)

        assert result.choices == []

    def test_generate_stream_uses_request_adapter(self) -> None:
        """generate_stream uses configured request adapter with stream flag."""
        request_adapter = _TestRequestAdapter()
        svc, transport = _make_service(
            adapter_set=LLMAdapterSet(
                request_adapter=request_adapter,
                completion_adapter=build_default_adapter_set().completion_adapter,
                stream_adapter=build_default_adapter_set().stream_adapter,
            )
        )
        streaming = StreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=MagicMock(),
        )
        transport.send.return_value = streaming

        request = LLMGenerateRequest(messages=[{"role": "user", "content": "Hello"}])
        svc.generate_stream(request)

        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content or b"{}") == {
            "input": [{"role": "user", "content": "Hello"}],
            "streaming": True,
        }
        assert request_adapter.calls == [(True, None)]

    def test_parse_stream_line_handles_sse_and_done_marker(self) -> None:
        """parse_stream_line parses SSE data lines and ignores [DONE]."""
        line = (
            "data: "
            '{"id":"chunk-1","choices":[{"index":0,'
            '"delta":{"role":"assistant","content":"H"}}]}'
        )
        chunk = LLMService.parse_stream_line(line)

        assert chunk is not None
        assert chunk.id == "chunk-1"
        assert chunk.choices[0].delta.content == "H"
        assert LLMService.parse_stream_line("data: [DONE]") is None
        assert LLMService.parse_stream_line("") is None
        assert LLMService.parse_stream_line(": heartbeat") is None

    def test_iter_stream_chunks_yields_parsed_chunks(self) -> None:
        """iter_stream_chunks yields normalized chunks from line stream."""
        line = (
            "data: "
            '{"id":"chunk-1","choices":[{"index":0,'
            '"delta":{"role":"assistant","content":"Hi"}}]}'
        )
        raw = _SyncLineRaw(
            [
                line,
                "data: [DONE]",
            ]
        )
        response = StreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=raw,
        )
        svc, _ = _make_service()

        chunks = list(svc.iter_stream_chunks(response))

        assert len(chunks) == 1
        assert chunks[0].choices[0].delta.content == "Hi"

    def test_iter_stream_chunks_merges_multiline_sse_event(self) -> None:
        """iter_stream_chunks merges multi-line SSE data into one event."""
        raw = _SyncLineRaw(
            [
                'data: {"id":"chunk-2","choices":[{"index":0,',
                'data: "delta":{"role":"assistant","content":"Hi"}}]}',
                "",
                "data: [DONE]",
                "",
            ]
        )
        response = StreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=raw,
        )
        svc, _ = _make_service()

        chunks = list(svc.iter_stream_chunks(response))

        assert len(chunks) == 1
        assert chunks[0].id == "chunk-2"
        assert chunks[0].choices[0].delta.content == "Hi"

    def test_iter_stream_chunks_raises_parse_error_on_invalid_payload(self) -> None:
        """iter_stream_chunks raises explicit parse error for invalid events."""
        raw = _SyncLineRaw(["data: not-json", ""])
        response = StreamingResponse(status_code=200, headers={}, content=b"", _raw=raw)
        svc, _ = _make_service()

        try:
            list(svc.iter_stream_chunks(response))
        except LLMStreamParseError:
            pass
        else:
            raise AssertionError("Expected LLMStreamParseError")

    def test_iter_stream_chunks_handles_bytes_comments_and_back_to_back_data(
        self,
    ) -> None:
        """iter_stream_chunks handles bytes lines and consecutive data events."""
        raw = _SyncBytesLineRaw(
            [
                b": heartbeat\n",
                (
                    b'data: {"id":"chunk-3","choices":[{"index":0,'
                    b'"delta":{"role":"assistant","content":"A"}}]}\n'
                ),
                (
                    b'data: {"id":"chunk-4","choices":[{"index":0,'
                    b'"delta":{"role":"assistant","content":"B"}}]}\n'
                ),
                (
                    b'  {"id":"chunk-5","choices":[{"index":0,'
                    b'"delta":{"role":"assistant","content":"C"}}]}\n'
                ),
            ]
        )
        response = StreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=raw,
        )
        svc, _ = _make_service()

        chunks = list(svc.iter_stream_chunks(response))

        assert [chunk.id for chunk in chunks] == ["chunk-3", "chunk-4", "chunk-5"]
        assert [chunk.choices[0].delta.content for chunk in chunks] == ["A", "B", "C"]

    def test_iter_stream_chunks_flushes_final_buffer_without_empty_line(self) -> None:
        """iter_stream_chunks emits final buffered SSE event at stream end."""
        raw = _SyncLineRaw(
            [
                (
                    'data: {"id":"chunk-final","choices":[{"index":0,'
                    '"delta":{"role":"assistant","content":"Z"}}]}'
                ),
            ]
        )
        response = StreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=raw,
        )
        svc, _ = _make_service()

        chunks = list(svc.iter_stream_chunks(response))

        assert len(chunks) == 1
        assert chunks[0].id == "chunk-final"

    def test_parse_stream_line_handles_non_sse_json_line(self) -> None:
        """parse_stream_line accepts raw JSON lines without data prefix."""
        chunk = LLMService.parse_stream_line(
            '{"id":"chunk-raw","choices":[{"index":0,"delta":{"role":"assistant","content":"R"}}]}'
        )

        assert chunk is not None
        assert chunk.id == "chunk-raw"

    def test_parse_stream_line_uses_provided_adapter_set(self) -> None:
        """parse_stream_line routes parsing through provided adapter set."""
        stream_adapter = _TestStreamAdapter()
        adapter_set = LLMAdapterSet(
            request_adapter=build_default_adapter_set().request_adapter,
            completion_adapter=build_default_adapter_set().completion_adapter,
            stream_adapter=stream_adapter,
        )

        chunk = LLMService.parse_stream_line(
            (
                'data: {"id":"chunk-custom","choices":[{"index":0,'
                '"delta":{"role":"assistant","content":"X"}}]}'
            ),
            adapter_set=adapter_set,
        )

        assert stream_adapter.calls == [
            '{"id":"chunk-custom","choices":[{"index":0,'
            '"delta":{"role":"assistant","content":"X"}}]}'
        ]
        assert chunk is not None
        assert chunk.id == "chunk-custom"

    def test_payload_adapter_object_must_return_dict(self) -> None:
        """Raise TypeError when adapter object returns a non-dict payload."""

        class _BadAdapterObject:
            def to_provider_payload(
                self,
                request: LLMGenerateRequest,
                *,
                stream: bool,
            ) -> list[str]:
                del request, stream
                return ["invalid"]

        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=_DUMMY_BASE_URL, transport=transport)
        with pytest.warns(DeprecationWarning, match="payload_adapter is deprecated"):
            svc = LLMService(client, payload_adapter=_BadAdapterObject())

        with pytest.raises(TypeError, match="dictionary payload"):
            svc.generate(
                LLMGenerateRequest(
                    messages=[{"role": "user", "content": "x"}],
                )
            )

    def test_constructor_rejects_non_callable_payload_adapter(self) -> None:
        """Raise TypeError when payload_adapter is neither callable nor adapter."""
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=_DUMMY_BASE_URL, transport=transport)

        with pytest.warns(DeprecationWarning, match="payload_adapter is deprecated"):
            with pytest.raises(TypeError, match="payload_adapter"):
                LLMService(client, payload_adapter=object())

    def test_payload_adapter_var_kwargs_supports_stream_keyword(self) -> None:
        """Detect ``**kwargs`` payload adapters as stream-compatible."""

        def payload_adapter(
            request: LLMGenerateRequest,
            **kwargs: Any,
        ) -> dict[str, Any]:
            return {
                "legacy_input": request.to_payload()["messages"],
                "legacy_stream": kwargs.get("stream", False),
            }

        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=_DUMMY_BASE_URL, transport=transport)
        with pytest.warns(DeprecationWarning, match="payload_adapter is deprecated"):
            svc = LLMService(client, payload_adapter=payload_adapter)
        streaming = StreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=MagicMock(),
        )
        transport.send.return_value = streaming

        svc.generate_stream(
            LLMGenerateRequest(messages=[{"role": "user", "content": "Hello"}])
        )

        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content or b"{}") == {
            "legacy_input": [{"role": "user", "content": "Hello"}],
            "legacy_stream": True,
        }

    def test_payload_adapter_signature_failure_defaults_stream_keyword(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Treat unknown signatures as stream-compatible for backward compatibility."""

        def payload_adapter(
            request: LLMGenerateRequest,
            **kwargs: Any,
        ) -> dict[str, Any]:
            return {
                "legacy_input": request.to_payload()["messages"],
                "legacy_stream": kwargs.get("stream", False),
            }

        monkeypatch.setattr(
            inspect,
            "signature",
            lambda _: (_ for _ in ()).throw(ValueError("no signature")),
        )

        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=_DUMMY_BASE_URL, transport=transport)
        with pytest.warns(DeprecationWarning, match="payload_adapter is deprecated"):
            svc = LLMService(client, payload_adapter=payload_adapter)
        streaming = StreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=MagicMock(),
        )
        transport.send.return_value = streaming

        svc.generate_stream(
            LLMGenerateRequest(messages=[{"role": "user", "content": "Hello"}])
        )

        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content or b"{}") == {
            "legacy_input": [{"role": "user", "content": "Hello"}],
            "legacy_stream": True,
        }


class TestAsyncLLMService:
    """Tests for AsyncLLMService."""

    async def test_generate_posts_expected_payload_and_parses_completion(self) -> None:
        """Async generate sends payload and parses completion model."""
        payload = {
            "id": "cmp-2",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Done"},
                    "finish_reason": "stop",
                }
            ],
        }
        svc, transport = _make_async_service(content=_json_bytes(payload))
        request = LLMGenerateRequest(messages=[{"role": "user", "content": "Hello"}])

        result = await svc.generate(request)

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith("/v1/llm/chat/completions")
        assert json.loads(sent.content or b"{}") == {
            "messages": [{"role": "user", "content": "Hello"}],
        }
        assert result.choices[0].message.content == "Done"

    async def test_generate_stream_uses_stream_request(self) -> None:
        """Async generate_stream enables stream mode."""
        svc, transport = _make_async_service()
        streaming = AsyncStreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=MagicMock(),
        )
        transport.send.return_value = streaming

        request = LLMGenerateRequest(messages=[{"role": "user", "content": "Hello"}])
        result = await svc.generate_stream(request)

        sent = transport.send.call_args[0][0]
        assert sent.stream is True
        assert json.loads(sent.content or b"{}") == {
            "messages": [{"role": "user", "content": "Hello"}],
            "options": {"stream": True},
        }
        assert isinstance(result, AsyncStreamingResponse)

    async def test_generate_uses_request_and_response_adapters(self) -> None:
        """Async generate uses adapter set for request and response mapping."""
        request_adapter = _TestRequestAdapter()
        response_adapter = _TestResponseAdapter()

        payload = {"text": "ok"}
        svc, transport = _make_async_service(
            content=_json_bytes(payload),
            adapter_set=LLMAdapterSet(
                request_adapter=request_adapter,
                completion_adapter=response_adapter,
                stream_adapter=build_default_adapter_set().stream_adapter,
            ),
        )

        request = LLMGenerateRequest(
            messages=[{"role": "user", "content": "Hello"}],
            model="demo",
        )
        result = await svc.generate(request)

        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content or b"{}") == {
            "input": [{"role": "user", "content": "Hello"}],
            "streaming": False,
        }
        assert request_adapter.calls == [(False, "demo")]
        assert result.choices[0].message.content == "ok"

    async def test_generate_stream_supports_payload_adapter_with_stream_kwarg(
        self,
    ) -> None:
        """Async service supports payload_adapter(request, stream=...) callables."""

        def payload_adapter(
            request: LLMGenerateRequest,
            *,
            stream: bool,
        ) -> dict[str, Any]:
            return {
                "legacy_input": request.to_payload()["messages"],
                "legacy_stream": stream,
            }

        transport = MockAsyncTransport(status_code=200, content=b"{}")
        client = AsyncAPIClient(base_url=_DUMMY_BASE_URL, transport=transport)
        with pytest.warns(DeprecationWarning, match="payload_adapter is deprecated"):
            svc = AsyncLLMService(client, payload_adapter=payload_adapter)
        streaming = AsyncStreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=MagicMock(),
        )
        transport.send.return_value = streaming

        request = LLMGenerateRequest(messages=[{"role": "user", "content": "Hello"}])
        await svc.generate_stream(request)

        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content or b"{}") == {
            "legacy_input": [{"role": "user", "content": "Hello"}],
            "legacy_stream": True,
        }

    async def test_generate_falls_back_for_non_object_completion_payload(self) -> None:
        """Async generate normalizes non-object JSON responses to empty payload."""
        svc, _ = _make_async_service(content=_json_bytes(["unexpected"]))
        request = LLMGenerateRequest(messages=[{"role": "user", "content": "Hi"}])

        result = await svc.generate(request)

        assert result.choices == []

    async def test_generate_stream_uses_request_adapter(self) -> None:
        """Async generate_stream uses configured request adapter."""
        request_adapter = _TestRequestAdapter()
        svc, transport = _make_async_service(
            adapter_set=LLMAdapterSet(
                request_adapter=request_adapter,
                completion_adapter=build_default_adapter_set().completion_adapter,
                stream_adapter=build_default_adapter_set().stream_adapter,
            )
        )
        streaming = AsyncStreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=MagicMock(),
        )
        transport.send.return_value = streaming

        request = LLMGenerateRequest(messages=[{"role": "user", "content": "Hello"}])
        await svc.generate_stream(request)

        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content or b"{}") == {
            "input": [{"role": "user", "content": "Hello"}],
            "streaming": True,
        }
        assert request_adapter.calls == [(True, None)]

    async def test_iter_stream_chunks_yields_parsed_chunks(self) -> None:
        """Async iter_stream_chunks yields normalized chunks from lines."""
        line = (
            "data: "
            '{"id":"chunk-a","choices":[{"index":0,'
            '"delta":{"role":"assistant","content":"A"}}]}'
        )
        raw = _AsyncLineRaw(
            [
                line,
                "data: [DONE]",
            ]
        )
        response = AsyncStreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=raw,
        )
        svc, _ = _make_async_service()

        chunks = [chunk async for chunk in svc.iter_stream_chunks(response)]

        assert len(chunks) == 1
        assert chunks[0].choices[0].delta.content == "A"

    async def test_iter_stream_chunks_merges_multiline_sse_event(self) -> None:
        """Async iter_stream_chunks merges multi-line SSE data events."""
        raw = _AsyncLineRaw(
            [
                'data: {"id":"chunk-b","choices":[{"index":0,',
                'data: "delta":{"role":"assistant","content":"B"}}]}',
                "",
                "data: [DONE]",
                "",
            ]
        )
        response = AsyncStreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=raw,
        )
        svc, _ = _make_async_service()

        chunks = [chunk async for chunk in svc.iter_stream_chunks(response)]

        assert len(chunks) == 1
        assert chunks[0].id == "chunk-b"
        assert chunks[0].choices[0].delta.content == "B"

    async def test_iter_stream_chunks_raises_parse_error_on_invalid_payload(
        self,
    ) -> None:
        """Async iter_stream_chunks raises explicit parse errors."""
        raw = _AsyncLineRaw(["data: not-json", ""])
        response = AsyncStreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=raw,
        )
        svc, _ = _make_async_service()

        iterator = svc.iter_stream_chunks(response)
        try:
            await anext(iterator)
        except LLMStreamParseError:
            pass
        else:
            raise AssertionError("Expected LLMStreamParseError")

    async def test_iter_stream_chunks_handles_comment_flush_non_data_and_tail(
        self,
    ) -> None:
        """Async stream parsing handles comment, flush on non-data, and tail."""
        raw = _AsyncLineRaw(
            [
                ": keepalive",
                (
                    'data: {"id":"achunk-1","choices":[{"index":0,'
                    '"delta":{"role":"assistant","content":"A"}}]}'
                ),
                (
                    '{"id":"achunk-2","choices":[{"index":0,'
                    '"delta":{"role":"assistant","content":"B"}}]}'
                ),
                (
                    'data: {"id":"achunk-3","choices":[{"index":0,'
                    '"delta":{"role":"assistant","content":"C"}}]}'
                ),
            ]
        )
        response = AsyncStreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=raw,
        )
        svc, _ = _make_async_service()

        chunks = [chunk async for chunk in svc.iter_stream_chunks(response)]

        assert [chunk.id for chunk in chunks] == ["achunk-1", "achunk-2", "achunk-3"]

    def test_parse_stream_line_delegates_to_sync_parser(self) -> None:
        """Async parse_stream_line delegates to sync implementation."""
        chunk = AsyncLLMService.parse_stream_line(
            'data: {"id":"chunk-delegate","choices":[{"index":0,'
            '"delta":{"role":"assistant","content":"D"}}]}'
        )

        assert chunk is not None
        assert chunk.id == "chunk-delegate"

    def test_parse_stream_line_supports_custom_adapter_set(self) -> None:
        """Async parse_stream_line supports explicit adapter-set parsing."""
        stream_adapter = _TestStreamAdapter()
        adapter_set = LLMAdapterSet(
            request_adapter=build_default_adapter_set().request_adapter,
            completion_adapter=build_default_adapter_set().completion_adapter,
            stream_adapter=stream_adapter,
        )

        chunk = AsyncLLMService.parse_stream_line(
            (
                'data: {"id":"chunk-adelegate","choices":[{"index":0,'
                '"delta":{"role":"assistant","content":"A"}}]}'
            ),
            adapter_set=adapter_set,
        )

        assert stream_adapter.calls == [
            '{"id":"chunk-adelegate","choices":[{"index":0,'
            '"delta":{"role":"assistant","content":"A"}}]}'
        ]
        assert chunk is not None
        assert chunk.id == "chunk-adelegate"
