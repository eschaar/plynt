"""Generic LLM service contracts built on plynth API services.

This module provides sync and async service implementations that operate on
neutral LLM contract models. Provider-specific behavior can be carried via
opaque extension fields without leaking into this layer.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from json import JSONDecodeError
from typing import Any

from plynth.base.response import AsyncStreamingResponse, StreamingResponse
from plynth.connectors.llm.adapters.base import (
    LLMAdapterSet,
    build_default_adapter_set,
)
from plynth.connectors.llm.models import (
    LLMCompletion,
    LLMGenerateRequest,
    LLMStreamChunk,
)
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import Renderer
from plynth.http.service import APIService, AsyncAPIService

__all__ = [
    "AsyncLLMService",
    "LLMAdapterSet",
    "LLMService",
    "LLMStreamParseError",
    "build_default_adapter_set",
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
        adapter_set: LLMAdapterSet | None = None,
    ) -> None:
        """Initialize LLMService."""
        super().__init__(client, renderer=renderer)
        self._base_path = base_path.rstrip("/")
        self._adapter_set = adapter_set or build_default_adapter_set()

    def _serialize_request(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Return request payload using configured adapter set."""
        return self._adapter_set.request_adapter.to_provider_payload(
            request,
            stream=stream,
        )

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
        if not isinstance(payload, dict):
            payload = {}

        normalized_payload = (
            self._adapter_set.completion_adapter.to_neutral_completion_payload(payload)
        )
        return LLMCompletion.from_payload(normalized_payload)

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

        try:
            return build_default_adapter_set().stream_adapter.parse_event_payload(
                stripped
            )
        except ValueError as exc:
            raise LLMStreamParseError(
                "Failed to parse LLM stream event payload"
            ) from exc

    def iter_stream_chunks(
        self,
        response: StreamingResponse,
    ) -> Iterator[LLMStreamChunk]:
        """Yield parsed stream chunks from a streaming response."""
        lines = (_line_to_text(line) for line in response.iter_lines())
        for event_payload in _iter_sse_event_data(lines):
            try:
                chunk = self._adapter_set.stream_adapter.parse_event_payload(
                    event_payload
                )
            except ValueError as exc:
                raise LLMStreamParseError(
                    "Failed to parse LLM stream event payload"
                ) from exc
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
        adapter_set: LLMAdapterSet | None = None,
    ) -> None:
        """Initialize AsyncLLMService."""
        super().__init__(client, renderer=renderer)
        self._base_path = base_path.rstrip("/")
        self._adapter_set = adapter_set or build_default_adapter_set()

    def _serialize_request(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Return request payload using configured adapter set."""
        return self._adapter_set.request_adapter.to_provider_payload(
            request,
            stream=stream,
        )

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
        if not isinstance(payload, dict):
            payload = {}

        normalized_payload = (
            self._adapter_set.completion_adapter.to_neutral_completion_payload(payload)
        )
        return LLMCompletion.from_payload(normalized_payload)

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
            try:
                chunk = self._adapter_set.stream_adapter.parse_event_payload(
                    event_payload
                )
            except ValueError as exc:
                raise LLMStreamParseError(
                    "Failed to parse LLM stream event payload"
                ) from exc
            if chunk is not None:
                yield chunk
