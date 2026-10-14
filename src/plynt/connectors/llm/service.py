"""Generic LLM service contracts built on plynt API services.

This module provides sync and async service implementations that operate on
neutral LLM contract models. Provider-specific behavior can be carried via
opaque extension fields without leaking into this layer.
"""

from __future__ import annotations

import inspect
import json
import warnings
from collections.abc import AsyncIterator, Iterator
from json import JSONDecodeError
from typing import Any

from plynt.base.response import AsyncStreamingResponse, StreamingResponse
from plynt.connectors.llm.adapters.base import (
    LLMAdapterSet,
    LLMRequestAdapter,
    LLMStreamAdapter,
    build_default_adapter_set,
)
from plynt.connectors.llm.models import (
    LLMCompletion,
    LLMGenerateRequest,
    LLMStreamChunk,
)
from plynt.http.client import APIClient, AsyncAPIClient
from plynt.http.renderer import Renderer
from plynt.http.service import APIService, AsyncAPIService

__all__ = [
    "AsyncLLMService",
    "LLMAdapterSet",
    "LLMService",
    "LLMStreamParseError",
    "build_default_adapter_set",
]


class LLMStreamParseError(ValueError):
    """Signal that a provider stream payload could not be parsed."""


class _SSEEventDataParser:
    """Utility parser that assembles logical SSE event payloads."""

    @staticmethod
    def line_to_text(line: str | bytes) -> str:
        """Normalize one stream line value to text."""
        if isinstance(line, bytes):
            return line.decode("utf-8", errors="replace")
        return line

    @staticmethod
    def is_complete_json(data_lines: list[str]) -> bool:
        """Return True when buffered SSE data lines form complete JSON."""
        if not data_lines:
            return False

        try:
            json.loads("\n".join(data_lines))
        except JSONDecodeError:
            return False
        return True

    @staticmethod
    def consume_data_value(
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

        if _SSEEventDataParser.is_complete_json(data_lines):
            emitted_events.append("\n".join(data_lines))
            data_lines = []

        data_lines.append(data_value)
        return emitted_events, data_lines

    @staticmethod
    def iter_event_data(lines: Iterator[str]) -> Iterator[str]:
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
                emitted_events, data_lines = _SSEEventDataParser.consume_data_value(
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

    @staticmethod
    async def aiter_event_data(lines: AsyncIterator[str]) -> AsyncIterator[str]:
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
                emitted_events, data_lines = _SSEEventDataParser.consume_data_value(
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


_DEFAULT_ADAPTER_SET = build_default_adapter_set()


class _PayloadAdapterWrapperBase:
    """Shared validation behavior for request-adapter wrappers."""

    @staticmethod
    def _ensure_payload_dict(payload: Any) -> dict[str, Any]:
        """Validate provider payload shape returned by wrapped adapters."""
        if not isinstance(payload, dict):
            raise TypeError("payload_adapter must return a dictionary payload")
        return payload


class _AdapterObjectWrapper(_PayloadAdapterWrapperBase):
    """Bridge adapter objects exposing ``to_provider_payload``."""

    def __init__(self, adapter_object: Any) -> None:
        self._adapter_object = adapter_object

    def to_provider_payload(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Delegate to wrapped adapter object's request serialization method."""
        payload = self._adapter_object.to_provider_payload(
            request,
            stream=stream,
        )
        return self._ensure_payload_dict(payload)


class _LegacyPayloadAdapterWrapper(_PayloadAdapterWrapperBase):
    """Bridge legacy payload callables to LLMRequestAdapter contract."""

    def __init__(self, adapter_callable: Any) -> None:
        self._adapter_callable = adapter_callable
        self._supports_stream_kw = self._detect_stream_kw_support(adapter_callable)

    @staticmethod
    def _detect_stream_kw_support(adapter_callable: Any) -> bool:
        """Detect whether callable accepts the ``stream`` keyword argument."""
        try:
            signature = inspect.signature(adapter_callable)
        except (TypeError, ValueError):
            # Unknown signature: keep backward-compatible behavior.
            return True

        for parameter in signature.parameters.values():
            if parameter.kind == inspect.Parameter.VAR_KEYWORD:
                return True
            if parameter.name == "stream":
                return True
        return False

    def to_provider_payload(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Delegate to legacy callable with stable stream argument handling."""
        if self._supports_stream_kw:
            payload = self._adapter_callable(request, stream=stream)
        else:
            payload = self._adapter_callable(request)
        return self._ensure_payload_dict(payload)


def _coerce_payload_adapter(payload_adapter: Any) -> LLMRequestAdapter:
    """Convert legacy payload-adapter values to request-adapter contract."""
    to_provider_payload = getattr(payload_adapter, "to_provider_payload", None)

    if callable(to_provider_payload):
        return _AdapterObjectWrapper(payload_adapter)

    if not callable(payload_adapter):
        raise TypeError("payload_adapter must be callable or LLMRequestAdapter")

    return _LegacyPayloadAdapterWrapper(payload_adapter)


def _resolve_adapter_set(
    adapter_set: LLMAdapterSet | None,
    payload_adapter: Any,
) -> LLMAdapterSet:
    """Resolve adapter set with support for deprecated payload_adapter alias."""
    if payload_adapter is None:
        return adapter_set or build_default_adapter_set()

    if adapter_set is not None:
        raise ValueError("Use either adapter_set or payload_adapter, not both")

    warnings.warn(
        "payload_adapter is deprecated; pass adapter_set=request_adapter instead",
        DeprecationWarning,
        stacklevel=3,
    )
    default_set = build_default_adapter_set()
    return LLMAdapterSet(
        request_adapter=_coerce_payload_adapter(payload_adapter),
        completion_adapter=default_set.completion_adapter,
        stream_adapter=default_set.stream_adapter,
    )


def _parse_stream_event_payload(
    payload_line: str,
    *,
    stream_adapter: LLMStreamAdapter,
) -> LLMStreamChunk | None:
    """Parse one stream payload and normalize parser failures."""
    try:
        return stream_adapter.parse_event_payload(payload_line)
    except ValueError as exc:
        raise LLMStreamParseError("Failed to parse LLM stream event payload") from exc


class LLMService(APIService):
    """Send synchronous generation requests through a neutral LLM contract.

    The default endpoint path matches common chat-completion routes and can be
    overridden per call when a provider uses a different endpoint.
    """

    def __init__(
        self,
        client: APIClient,
        *,
        renderer: Renderer | None = None,
        base_path: str = "/v1/llm",
        adapter_set: LLMAdapterSet | None = None,
        payload_adapter: Any = None,
    ) -> None:
        """Initialize a synchronous LLM service instance.

        Args:
            client: Configured HTTP API client.
            renderer: Optional payload renderer; defaults to the service
                renderer from the base class.
            base_path: Prefix path used for provider calls.
            adapter_set: Optional adapter set for provider mapping.
            payload_adapter: Deprecated request adapter alias kept for backward
                compatibility.

        """
        super().__init__(client, renderer=renderer)
        self._base_path = base_path.rstrip("/")
        self._adapter_set = _resolve_adapter_set(adapter_set, payload_adapter)

    def _serialize_request(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Return a provider payload using the configured adapter set."""
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
        """Generate a non-streaming completion.

        Args:
            request: Neutral generation request payload.
            path: Provider endpoint path under ``base_path``.

        Returns:
            Normalized completion model.

        """
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
        """Open a streaming generation response.

        Args:
            request: Neutral generation request payload.
            path: Provider endpoint path under ``base_path``.

        Returns:
            Streaming HTTP response from the provider.

        """
        return self._client.stream(
            "POST",
            f"{self._base_path}{path}",
            content=self._renderer.render(
                self._serialize_request(request, stream=True)
            ),
        )

    @staticmethod
    def parse_stream_line(
        line: str,
        *,
        adapter_set: LLMAdapterSet | None = None,
    ) -> LLMStreamChunk | None:
        """Parse one SSE or JSON payload line into a stream chunk.

        Returns ``None`` for empty lines, comments, and terminal ``[DONE]``
        markers. Pass ``adapter_set`` for provider-specific stream formats.

        This helper parses only one payload line. Use ``iter_stream_chunks``
        for production stream processing, because it handles SSE framing,
        multi-line ``data:`` events, and incremental buffering.

        Args:
            line: Raw line emitted by the provider stream.
            adapter_set: Optional adapter set for provider-specific parsing.

        Returns:
            Parsed stream chunk, or ``None`` for ignorable lines.

        Raises:
            LLMStreamParseError: If the payload line cannot be parsed.

        """
        stripped = line.strip()
        if not stripped or stripped.startswith(":"):
            return None

        if stripped.startswith("data:"):
            stripped = stripped[len("data:") :].strip()

        stream_adapter = (
            adapter_set.stream_adapter
            if adapter_set is not None
            else _DEFAULT_ADAPTER_SET.stream_adapter
        )
        return _parse_stream_event_payload(
            stripped,
            stream_adapter=stream_adapter,
        )

    def iter_stream_chunks(
        self,
        response: StreamingResponse,
    ) -> Iterator[LLMStreamChunk]:
        """Yield stream chunks from a streaming response.

        Args:
            response: Streaming response returned by ``generate_stream``.

        Yields:
            Parsed stream chunks in provider emission order.

        Raises:
            LLMStreamParseError: If any event payload cannot be parsed.

        """
        lines = (
            _SSEEventDataParser.line_to_text(line) for line in response.iter_lines()
        )
        for event_payload in _SSEEventDataParser.iter_event_data(lines):
            chunk = _parse_stream_event_payload(
                event_payload,
                stream_adapter=self._adapter_set.stream_adapter,
            )
            if chunk is not None:
                yield chunk


class AsyncLLMService(AsyncAPIService):
    """Send asynchronous generation requests through a neutral LLM contract."""

    def __init__(
        self,
        client: AsyncAPIClient,
        *,
        renderer: Renderer | None = None,
        base_path: str = "/v1/llm",
        adapter_set: LLMAdapterSet | None = None,
        payload_adapter: Any = None,
    ) -> None:
        """Initialize an asynchronous LLM service instance.

        Args:
            client: Configured async HTTP API client.
            renderer: Optional payload renderer; defaults to the service
                renderer from the base class.
            base_path: Prefix path used for provider calls.
            adapter_set: Optional adapter set for provider mapping.
            payload_adapter: Deprecated request adapter alias kept for backward
                compatibility.

        """
        super().__init__(client, renderer=renderer)
        self._base_path = base_path.rstrip("/")
        self._adapter_set = _resolve_adapter_set(adapter_set, payload_adapter)

    def _serialize_request(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Return a provider payload using the configured adapter set."""
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
        """Generate a non-streaming completion asynchronously.

        Args:
            request: Neutral generation request payload.
            path: Provider endpoint path under ``base_path``.

        Returns:
            Normalized completion model.

        """
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
        """Open an asynchronous streaming generation response.

        Args:
            request: Neutral generation request payload.
            path: Provider endpoint path under ``base_path``.

        Returns:
            Async streaming HTTP response from the provider.

        """
        return await self._client.stream(
            "POST",
            f"{self._base_path}{path}",
            content=self._renderer.render(
                self._serialize_request(request, stream=True)
            ),
        )

    @staticmethod
    def parse_stream_line(
        line: str,
        *,
        adapter_set: LLMAdapterSet | None = None,
    ) -> LLMStreamChunk | None:
        """Parse one SSE or JSON payload line into a stream chunk.

        This helper delegates to ``LLMService.parse_stream_line`` and stays a
        single-line utility. Prefer ``iter_stream_chunks`` for full async
        stream processing.

        Args:
            line: Raw line emitted by the provider stream.
            adapter_set: Optional adapter set for provider-specific parsing.

        Returns:
            Parsed stream chunk, or ``None`` for ignorable lines.

        """
        return LLMService.parse_stream_line(line, adapter_set=adapter_set)

    async def iter_stream_chunks(
        self,
        response: AsyncStreamingResponse,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Yield stream chunks from an async streaming response.

        Args:
            response: Async streaming response returned by
                ``generate_stream``.

        Yields:
            Parsed stream chunks in provider emission order.

        Raises:
            LLMStreamParseError: If any event payload cannot be parsed.

        """
        lines = (
            _SSEEventDataParser.line_to_text(line)
            async for line in response.aiter_lines()
        )
        async for event_payload in _SSEEventDataParser.aiter_event_data(lines):
            chunk = _parse_stream_event_payload(
                event_payload,
                stream_adapter=self._adapter_set.stream_adapter,
            )
            if chunk is not None:
                yield chunk
