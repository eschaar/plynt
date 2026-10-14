"""Tests for base LLM adapter contracts and defaults."""

from __future__ import annotations

from typing import Any, cast

import pytest

from plynt.connectors.llm.adapters.base import (
    DefaultLLMCompletionAdapter,
    DefaultLLMRequestAdapter,
    DefaultLLMStreamAdapter,
    LLMCompletionAdapter,
    LLMRequestAdapter,
    LLMStreamAdapter,
    RoutedEventStreamAdapter,
)
from plynt.connectors.llm.models import LLMExecutionOptions, LLMGenerateRequest


class TestDefaultLLMRequestAdapter:
    """Tests for default neutral request serialization."""

    def test_to_provider_payload_keeps_existing_stream_flag_for_non_stream(
        self,
    ) -> None:
        """Adapter keeps the request payload unchanged for non-streaming mode."""
        adapter = DefaultLLMRequestAdapter()
        request = LLMGenerateRequest(
            messages=[{"role": "user", "content": "Hello"}],
            options=LLMExecutionOptions(stream=True),
        )

        payload = adapter.to_provider_payload(request, stream=False)

        assert payload == {
            "messages": [{"role": "user", "content": "Hello"}],
            "options": {"stream": True},
        }

    def test_to_provider_payload_sets_stream_true_when_requested(self) -> None:
        """Adapter forces options.stream when streaming is requested."""
        adapter = DefaultLLMRequestAdapter()
        request = LLMGenerateRequest(messages=[{"role": "user", "content": "Hi"}])

        payload = adapter.to_provider_payload(request, stream=True)

        assert payload == {
            "messages": [{"role": "user", "content": "Hi"}],
            "options": {"stream": True},
        }


class TestDefaultLLMCompletionAdapter:
    """Tests for default completion pass-through behavior."""

    def test_to_neutral_completion_payload_returns_payload_unchanged(self) -> None:
        """Adapter returns payload unchanged when already neutral."""
        adapter = DefaultLLMCompletionAdapter()
        payload = {"choices": [{"index": 0}], "usage": {"total_tokens": 1}}

        normalized = adapter.to_neutral_completion_payload(payload)

        assert normalized is payload


class TestDefaultLLMStreamAdapter:
    """Tests for default JSON stream parsing."""

    def test_parse_event_payload_returns_none_for_done_marker(self) -> None:
        """Adapter ignores terminal done markers."""
        adapter = DefaultLLMStreamAdapter()

        result = adapter.parse_event_payload("[DONE]")

        assert result is None

    def test_parse_event_payload_parses_json_chunk(self) -> None:
        """Adapter parses a JSON payload into a normalized stream chunk."""
        adapter = DefaultLLMStreamAdapter()

        chunk = adapter.parse_event_payload(
            '{"id":"chunk-1","choices":[{"index":0,'
            '"delta":{"role":"assistant","content":"A"}}]}'
        )

        assert chunk is not None
        assert chunk.id == "chunk-1"
        assert chunk.choices[0].delta.content == "A"

    def test_parse_event_payload_raises_on_invalid_json(self) -> None:
        """Adapter raises ValueError when JSON payload cannot be parsed."""
        adapter = DefaultLLMStreamAdapter()

        with pytest.raises(ValueError):
            adapter.parse_event_payload("not-json")


class TestAdapterContracts:
    """Tests for defensive contract stubs on protocol and base adapters."""

    def test_request_protocol_stub_raises_not_implemented(self) -> None:
        """Request protocol stub raises NotImplementedError when called directly."""
        request = LLMGenerateRequest(messages=[{"role": "user", "content": "x"}])

        with pytest.raises(NotImplementedError):
            LLMRequestAdapter.to_provider_payload(
                cast(Any, object()),
                request,
                stream=False,
            )

    def test_completion_protocol_stub_raises_not_implemented(self) -> None:
        """Completion protocol stub raises NotImplementedError when called directly."""
        with pytest.raises(NotImplementedError):
            LLMCompletionAdapter.to_neutral_completion_payload(cast(Any, object()), {})

    def test_routed_adapter_event_parser_stub_raises_not_implemented(self) -> None:
        """Routed stream adapter base requires event parser mapping override."""
        with pytest.raises(NotImplementedError):
            RoutedEventStreamAdapter().get_event_parsers()

    def test_stream_protocol_stub_raises_not_implemented(self) -> None:
        """Stream protocol stub raises NotImplementedError when called directly."""
        with pytest.raises(NotImplementedError):
            LLMStreamAdapter.parse_event_payload(cast(Any, object()), "{}")
