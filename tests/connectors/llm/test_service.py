"""Tests for LLMService and AsyncLLMService."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import MagicMock

from plynth.base.response import AsyncStreamingResponse, StreamingResponse
from plynth.connectors.llm import AsyncLLMService, LLMGenerateRequest, LLMService
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import JSONRenderer
from tests.conftest import MockAsyncTransport, MockSyncTransport

_JSON_RENDERER = JSONRenderer()
_DUMMY_BASE_URL = "https://llm.example.com"


class _SyncLineRaw:
    """Simple raw stream stub with iter_lines()."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def iter_lines(self) -> Iterator[str]:
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
) -> tuple[LLMService, MockSyncTransport]:
    """Build LLMService with a sync mock transport."""
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = APIClient(base_url=_DUMMY_BASE_URL, transport=transport)
    return LLMService(client), transport


def _make_async_service(
    *,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[AsyncLLMService, MockAsyncTransport]:
    """Build AsyncLLMService with an async mock transport."""
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncAPIClient(base_url=_DUMMY_BASE_URL, transport=transport)
    return AsyncLLMService(client), transport


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
        response = StreamingResponse(status_code=200, headers={}, content=b"", _raw=raw)
        svc, _ = _make_service()

        chunks = list(svc.iter_stream_chunks(response))

        assert len(chunks) == 1
        assert chunks[0].choices[0].delta.content == "Hi"


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
