"""Generic LLM service contracts built on plynth API services.

This module provides sync and async service implementations that operate on
neutral LLM contract models. Provider-specific behavior can be carried via
opaque extension fields without leaking into this layer.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable, Iterator
from json import JSONDecodeError
from typing import Any

from plynth.base.response import AsyncStreamingResponse, StreamingResponse
from plynth.connectors.llm.models import (
    LLMCompletion,
    LLMGenerateRequest,
    LLMStreamChunk,
)
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import Renderer
from plynth.http.service import APIService, AsyncAPIService

LLMRequestPayloadAdapter = Callable[[LLMGenerateRequest, bool], dict[str, Any]]

__all__ = [
    "AsyncLLMService",
    "LLMRequestPayloadAdapter",
    "LLMService",
    "LLMStreamParseError",
]


class LLMStreamParseError(ValueError):
    """Raised when a stream event payload cannot be parsed."""


def _line_to_text(line: str | bytes) -> str:
    """Normalize one stream line to text."""
    if isinstance(line, bytes):
        return line.decode("utf-8", errors="replace")
    return line


def _is_complete_json(data_lines: list[str]) -> bool:
    """Return True when buffered SSE data lines form a complete JSON value."""
    if not data_lines:
        return False

    try:
        json.loads("\n".join(data_lines))
    except JSONDecodeError:
        return False
    return True


def _consume_sse_data_value(
    data_lines: list[str],
    data_value: str,
) -> tuple[list[str], list[str]]:
    """Consume one SSE ``data:`` value and return emitted events + buffer."""
    emitted_events: list[str] = []

    if data_value == "[DONE]":
        if data_lines:
            emitted_events.append("\n".join(data_lines))
        emitted_events.append(data_value)
        return emitted_events, []

    if _is_complete_json(data_lines):
        emitted_events.append("\n".join(data_lines))
        data_lines = []

    data_lines.append(data_value)
    return emitted_events, data_lines


def _iter_sse_event_data(lines: Iterator[str]) -> Iterator[str]:
    """Yield logical SSE event payload strings from raw line iteration."""
    data_lines: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if not line:
            if data_lines:
                yield "\n".join(data_lines)
                data_lines.clear()
            continue

        if line.startswith(":"):
            continue

        if line.startswith("data:"):
            data_value = line[len("data:") :].lstrip()
            emitted_events, data_lines = _consume_sse_data_value(
                data_lines,
                data_value,
            )
            yield from emitted_events
            continue

        if data_lines:
            yield "\n".join(data_lines)
            data_lines.clear()

        yield line.strip()

    if data_lines:
        yield "\n".join(data_lines)


async def _aiter_sse_event_data(lines: AsyncIterator[str]) -> AsyncIterator[str]:
    """Yield logical SSE event payload strings from async line iteration."""
    data_lines: list[str] = []

    async for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if not line:
            if data_lines:
                yield "\n".join(data_lines)
                data_lines.clear()
            continue

        if line.startswith(":"):
            continue

        if line.startswith("data:"):
            data_value = line[len("data:") :].lstrip()
            emitted_events, data_lines = _consume_sse_data_value(
                data_lines,
                data_value,
            )
            for event in emitted_events:
                yield event
            continue

        if data_lines:
            yield "\n".join(data_lines)
            data_lines.clear()

        yield line.strip()

    if data_lines:
        yield "\n".join(data_lines)


class LLMService(APIService):
    """Synchronous, provider-agnostic LLM service.

    The default endpoint path follows common chat-completion conventions and
    can be overridden at call time when a provider uses a different route.
    """

    def __init__(
        self,
        client: APIClient,
        *,
        renderer: Renderer | None = None,
        base_path: str = "/v1/llm",
        payload_adapter: LLMRequestPayloadAdapter | None = None,
    ) -> None:
        """Initialize LLMService."""
        super().__init__(client, renderer=renderer)
        self._base_path = base_path.rstrip("/")
        self._payload_adapter = payload_adapter

    def _serialize_request(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Return request payload using optional provider adapter."""
        if self._payload_adapter is not None:
            return self._payload_adapter(request, stream)

        if stream:
            return request.with_stream(True).to_payload()
        return request.to_payload()

    def generate(
        self,
        request: LLMGenerateRequest,
        *,
        path: str = "/chat/completions",
    ) -> LLMCompletion:
        """Generate a non-streaming completion from the configured provider."""
        resp = self._client.post(
            f"{self._base_path}{path}",
            content=self._renderer.render(
                self._serialize_request(request, stream=False)
            ),
        )
        payload = json.loads(resp.content or b"{}")
        return LLMCompletion.from_payload(payload)

    def generate_stream(
        self,
        request: LLMGenerateRequest,
        *,
        path: str = "/chat/completions",
    ) -> StreamingResponse:
        """Generate a streaming completion response."""
        return self._client.stream(
            "POST",
            f"{self._base_path}{path}",
            content=self._renderer.render(
                self._serialize_request(request, stream=True)
            ),
        )

    @staticmethod
    def _parse_event_payload(payload_line: str) -> LLMStreamChunk | None:
        """Parse one event payload string into a normalized stream chunk."""
        stripped = payload_line.strip()
        if not stripped or stripped == "[DONE]":
            return None

        try:
            payload = json.loads(stripped)
        except JSONDecodeError as exc:
            raise LLMStreamParseError(
                "Failed to parse LLM stream event payload"
            ) from exc

        return LLMStreamChunk.from_payload(payload)

    @staticmethod
    def parse_stream_line(line: str) -> LLMStreamChunk | None:
        """Parse one SSE or JSON line into a normalized stream chunk.

        Returns ``None`` for empty lines, comments, and terminal ``[DONE]``
        markers.
        """
        stripped = line.strip()
        if not stripped or stripped.startswith(":"):
            return None

        if stripped.startswith("data:"):
            stripped = stripped[len("data:") :].strip()

        return LLMService._parse_event_payload(stripped)

    def iter_stream_chunks(
        self,
        response: StreamingResponse,
    ) -> Iterator[LLMStreamChunk]:
        """Yield parsed stream chunks from a streaming response."""
        lines = (_line_to_text(line) for line in response.iter_lines())
        for event_payload in _iter_sse_event_data(lines):
            chunk = self.parse_stream_line(event_payload)
            if chunk is not None:
                yield chunk


class AsyncLLMService(AsyncAPIService):
    """Asynchronous, provider-agnostic LLM service."""

    def __init__(
        self,
        client: AsyncAPIClient,
        *,
        renderer: Renderer | None = None,
        base_path: str = "/v1/llm",
        payload_adapter: LLMRequestPayloadAdapter | None = None,
    ) -> None:
        """Initialize AsyncLLMService."""
        super().__init__(client, renderer=renderer)
        self._base_path = base_path.rstrip("/")
        self._payload_adapter = payload_adapter

    def _serialize_request(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Return request payload using optional provider adapter."""
        if self._payload_adapter is not None:
            return self._payload_adapter(request, stream)

        if stream:
            return request.with_stream(True).to_payload()
        return request.to_payload()

    async def generate(
        self,
        request: LLMGenerateRequest,
        *,
        path: str = "/chat/completions",
    ) -> LLMCompletion:
        """Generate a non-streaming completion from the configured provider."""
        resp = await self._client.post(
            f"{self._base_path}{path}",
            content=self._renderer.render(
                self._serialize_request(request, stream=False)
            ),
        )
        payload = json.loads(resp.content or b"{}")
        return LLMCompletion.from_payload(payload)

    async def generate_stream(
        self,
        request: LLMGenerateRequest,
        *,
        path: str = "/chat/completions",
    ) -> AsyncStreamingResponse:
        """Generate a streaming completion response."""
        return await self._client.stream(
            "POST",
            f"{self._base_path}{path}",
            content=self._renderer.render(
                self._serialize_request(request, stream=True)
            ),
        )

    @staticmethod
    def parse_stream_line(line: str) -> LLMStreamChunk | None:
        """Parse one SSE or JSON line into a normalized stream chunk."""
        return LLMService.parse_stream_line(line)

    async def iter_stream_chunks(
        self,
        response: AsyncStreamingResponse,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Yield parsed stream chunks from an async streaming response."""
        lines = (_line_to_text(line) async for line in response.aiter_lines())
        async for event_payload in _aiter_sse_event_data(lines):
            chunk = self.parse_stream_line(event_payload)
            if chunk is not None:
                yield chunk
