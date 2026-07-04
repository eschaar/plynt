"""Generic LLM service contracts built on plynth API services.

This module provides sync and async service implementations that operate on
neutral LLM contract models. Provider-specific behavior can be carried via
opaque extension fields without leaking into this layer.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator

from plynth.base.response import AsyncStreamingResponse, StreamingResponse
from plynth.connectors.llm.models import (
    LLMCompletion,
    LLMGenerateRequest,
    LLMStreamChunk,
)
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import Renderer
from plynth.http.service import APIService, AsyncAPIService

__all__ = ["AsyncLLMService", "LLMService"]


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
    ) -> None:
        """Initialize LLMService."""
        super().__init__(client, renderer=renderer)
        self._base_path = base_path.rstrip("/")

    def generate(
        self,
        request: LLMGenerateRequest,
        *,
        path: str = "/chat/completions",
    ) -> LLMCompletion:
        """Generate a non-streaming completion from the configured provider."""
        resp = self._client.post(
            f"{self._base_path}{path}",
            content=self._renderer.render(request.to_payload()),
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
        stream_request = request.with_stream(True)
        return self._client.stream(
            "POST",
            f"{self._base_path}{path}",
            content=self._renderer.render(stream_request.to_payload()),
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

        if stripped == "[DONE]":
            return None

        payload = json.loads(stripped)
        return LLMStreamChunk.from_payload(payload)

    def iter_stream_chunks(
        self,
        response: StreamingResponse,
    ) -> Iterator[LLMStreamChunk]:
        """Yield parsed stream chunks from a streaming response."""
        for line in response.iter_lines():
            chunk = self.parse_stream_line(line)
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
    ) -> None:
        """Initialize AsyncLLMService."""
        super().__init__(client, renderer=renderer)
        self._base_path = base_path.rstrip("/")

    async def generate(
        self,
        request: LLMGenerateRequest,
        *,
        path: str = "/chat/completions",
    ) -> LLMCompletion:
        """Generate a non-streaming completion from the configured provider."""
        resp = await self._client.post(
            f"{self._base_path}{path}",
            content=self._renderer.render(request.to_payload()),
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
        stream_request = request.with_stream(True)
        return await self._client.stream(
            "POST",
            f"{self._base_path}{path}",
            content=self._renderer.render(stream_request.to_payload()),
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
        async for line in response.aiter_lines():
            chunk = self.parse_stream_line(line)
            if chunk is not None:
                yield chunk
