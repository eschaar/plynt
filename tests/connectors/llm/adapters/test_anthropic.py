"""Tests for Anthropic adapter helpers and service integration."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextvars import copy_context
from typing import Any

import pytest

from plynth.base.response import StreamingResponse
from plynth.connectors.llm.adapters.anthropic import (
    AnthropicMessagesCompletionAdapter,
    AnthropicMessagesRequestAdapter,
    AnthropicMessagesStreamAdapter,
    _AnthropicCompletionMapper,
    _AnthropicRequestMapper,
    _AnthropicStreamChunkFactory,
    build_anthropic_messages_adapter_set,
)
from plynth.connectors.llm.models import (
    LLMExecutionOptions,
    LLMGenerateRequest,
    LLMMessage,
    LLMToolDefinition,
)
from plynth.connectors.llm.service import AsyncLLMService, LLMService
from plynth.http.client import APIClient, AsyncAPIClient
from tests.conftest import MockAsyncTransport, MockSyncTransport

_DUMMY_BASE_URL = "https://llm.example.com"


def _json_bytes(data: Any) -> bytes:
    """Render arbitrary payload to JSON bytes."""
    return json.dumps(data).encode("utf-8")


class _SyncLineRaw:
    """Simple sync stream stub yielding provided lines."""

    def __init__(self, lines: list[str]) -> None:
        """Initialize _SyncLineRaw."""
        self._lines = lines

    def iter_lines(self) -> Iterator[str]:
        """Yield configured stream lines."""
        return iter(self._lines)


class TestAnthropicMessagesPayloadAdapter:
    """Tests for request payload mapping."""

    def test_maps_neutral_request_to_anthropic_shape(self) -> None:
        """Adapter maps neutral request fields to Anthropic payload fields."""
        adapter = AnthropicMessagesRequestAdapter()
        request = LLMGenerateRequest(
            model="claude-sonnet-4-20250514",
            messages=[
                {"role": "system", "content": "Be concise"},
                {"role": "user", "content": "Hello"},
            ],
            tools=[
                LLMToolDefinition(
                    name="get_weather",
                    description="Get weather",
                    input_schema={
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                )
            ],
            tool_choice={"type": "auto"},
            options=LLMExecutionOptions(
                temperature=0.3,
                max_tokens=512,
                top_p=0.8,
                metadata={"tenant": "acme"},
                provider_extensions={"thinking": {"type": "enabled"}},
            ),
            provider_extensions={"service_tier": "standard"},
        )

        payload = adapter.to_provider_payload(request, stream=False)

        assert payload["model"] == "claude-sonnet-4-20250514"
        assert payload["stream"] is False
        assert payload["max_tokens"] == 512
        assert payload["temperature"] == 0.3
        assert payload["top_p"] == 0.8
        assert payload["metadata"] == {"tenant": "acme"}
        assert payload["thinking"] == {"type": "enabled"}
        assert payload["service_tier"] == "standard"
        assert payload["system"] == "Be concise"
        assert payload["messages"] == [
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]}
        ]
        assert payload["tools"][0]["name"] == "get_weather"
        assert payload["tool_choice"] == {"type": "auto"}

    def test_maps_tool_result_message(self) -> None:
        """Adapter maps neutral tool result messages to Anthropic tool_result."""
        adapter = AnthropicMessagesRequestAdapter()
        request = LLMGenerateRequest(
            messages=[
                {
                    "role": "tool",
                    "content": "17C",
                    "tool_call_id": "toolu_123",
                }
            ]
        )

        payload = adapter.to_provider_payload(request, stream=False)

        assert payload["messages"] == [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_123",
                        "content": "17C",
                    }
                ],
            }
        ]

    def test_defaults_max_tokens_when_omitted(self) -> None:
        """Adapter provides safe max_tokens default when omitted."""
        adapter = AnthropicMessagesRequestAdapter()
        request = LLMGenerateRequest(messages=[LLMMessage(role="user", content="Hi")])

        payload = adapter.to_provider_payload(request, stream=False)

        assert payload["max_tokens"] == 1024


class TestAnthropicHelperFunctions:
    """Tests for Anthropic private helper branches."""

    def test_normalize_role(self) -> None:
        """Helper maps unsupported roles to user and keeps assistant."""
        assert _AnthropicRequestMapper.normalize_role("assistant") == "assistant"
        assert _AnthropicRequestMapper.normalize_role("developer") == "user"

    def test_message_content_as_text_variants(self) -> None:
        """Helper renders message content variants to text."""
        assert _AnthropicRequestMapper.message_content_as_text("hello") == "hello"
        assert _AnthropicRequestMapper.message_content_as_text(None) == ""
        assert (
            _AnthropicRequestMapper.message_content_as_text(
                [{"text": "a"}, 1, {"text": "b"}]
            )
            == "ab"
        )
        assert (
            _AnthropicRequestMapper.message_content_as_text(
                [{"text": "a"}, {"text": "b"}]
            )
            == "ab"
        )
        assert _AnthropicRequestMapper.message_content_as_text(
            [{"type": "image"}]
        ) == json.dumps([{"type": "image"}])
        assert _AnthropicRequestMapper.message_content_as_text({"a": 1}) == '{"a": 1}'

    def test_message_content_to_blocks_variants(self) -> None:
        """Helper converts content variants to Anthropic blocks."""
        assert _AnthropicRequestMapper.message_content_to_blocks("x") == [
            {"type": "text", "text": "x"}
        ]
        assert _AnthropicRequestMapper.message_content_to_blocks(None) == [
            {"type": "text", "text": ""}
        ]
        assert _AnthropicRequestMapper.message_content_to_blocks(
            [{"type": "text", "text": "y"}]
        ) == [{"type": "text", "text": "y"}]
        assert _AnthropicRequestMapper.message_content_to_blocks([1, 2]) == [
            {"type": "text", "text": ""}
        ]
        assert _AnthropicRequestMapper.message_content_to_blocks(42) == [
            {"type": "text", "text": "42"}
        ]

    def test_stream_event_kind_returns_unknown_for_unmapped_event(self) -> None:
        """Anthropic event-kind classifier returns unknown for unsupported events."""
        kind = _AnthropicStreamChunkFactory.classify_event_kind(
            "content_block_delta.custom"
        )

        assert kind == "unknown"

    def test_to_anthropic_message_with_llm_message(self) -> None:
        """Helper maps typed LLMMessage values correctly."""
        message = LLMMessage(role="assistant", content="ok")

        mapped = _AnthropicRequestMapper.to_anthropic_message(message)

        assert mapped == {
            "role": "assistant",
            "content": [{"type": "text", "text": "ok"}],
        }

    def test_to_anthropic_message_with_raw_dict(self) -> None:
        """Helper maps raw dict messages without pydantic conversion."""
        mapped = _AnthropicRequestMapper.to_anthropic_message(
            {"role": "user", "content": "raw"}
        )

        assert mapped == {
            "role": "user",
            "content": [{"type": "text", "text": "raw"}],
        }

    def test_extract_system_text_variants(self) -> None:
        """Helper extracts only system messages with non-empty text."""
        assert (
            _AnthropicRequestMapper.extract_system_text(
                {"role": "user", "content": "x"}
            )
            is None
        )
        assert (
            _AnthropicRequestMapper.extract_system_text(
                {"role": "system", "content": "sys"}
            )
            == "sys"
        )
        assert (
            _AnthropicRequestMapper.extract_system_text(
                {"role": "system", "content": None}
            )
            is None
        )

    def test_extract_text_content_non_list(self) -> None:
        """Helper returns empty string for non-list content payloads."""
        assert _AnthropicCompletionMapper.extract_text_content("not-a-list") == ""

    def test_extract_tool_calls_non_list_and_invalid_name(self) -> None:
        """Helper skips non-list and malformed tool blocks."""
        assert _AnthropicCompletionMapper.extract_tool_calls("not-a-list") == []
        assert (
            _AnthropicCompletionMapper.extract_tool_calls(
                [{"type": "tool_use", "input": {}}]
            )
            == []
        )

    def test_map_finish_reason_non_string(self) -> None:
        """Helper returns none for non-string stop reasons."""
        assert _AnthropicCompletionMapper.map_finish_reason(123) is None


class TestAnthropicMessagesCompletionAdapter:
    """Tests for response normalization."""

    def test_maps_text_and_tool_use_content(self) -> None:
        """Adapter maps Anthropic message content to neutral completion payload."""
        adapter = AnthropicMessagesCompletionAdapter()
        raw = {
            "id": "msg_123",
            "model": "claude-sonnet-4-20250514",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 6},
            "content": [
                {"type": "text", "text": "Hello"},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "lookup",
                    "input": {"id": 1},
                },
            ],
        }

        normalized = adapter.to_neutral_completion_payload(raw)

        assert normalized["id"] == "msg_123"
        assert normalized["choices"][0]["message"]["content"] == "Hello"
        assert normalized["choices"][0]["finish_reason"] == "stop"
        assert normalized["choices"][0]["message"]["tool_calls"][0]["id"] == "toolu_1"
        assert (
            normalized["provider_extensions"]["anthropic"]["event_kind"] == "completion"
        )
        assert (
            normalized["choices"][0]["message"]["tool_calls"][0]["function"][
                "arguments"
            ]
            == '{"id": 1}'
        )

    def test_ignores_malformed_content_blocks(self) -> None:
        """Adapter tolerates malformed content blocks without failing."""
        adapter = AnthropicMessagesCompletionAdapter()
        raw = {
            "id": "msg_bad",
            "stop_reason": "stop_sequence",
            "content": [123, {"type": "text", "text": "ok"}, {"type": "tool_use"}],
        }

        normalized = adapter.to_neutral_completion_payload(raw)

        assert normalized["choices"][0]["message"]["content"] == "ok"
        assert normalized["choices"][0]["finish_reason"] == "stop"

    def test_handles_string_tool_input(self) -> None:
        """Adapter keeps string tool input arguments unchanged."""
        adapter = AnthropicMessagesCompletionAdapter()
        raw = {
            "id": "msg_tool_string",
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_2",
                    "name": "lookup",
                    "input": '{"city":"AMS"}',
                }
            ],
        }

        normalized = adapter.to_neutral_completion_payload(raw)

        assert normalized["choices"][0]["finish_reason"] == "tool_use"
        assert (
            normalized["choices"][0]["message"]["tool_calls"][0]["function"][
                "arguments"
            ]
            == '{"city":"AMS"}'
        )


class TestAnthropicMessagesStreamAdapter:
    """Tests for stream-event normalization."""

    def test_maps_text_delta_events(self) -> None:
        """Stream adapter maps text deltas into neutral assistant chunks."""
        adapter = AnthropicMessagesStreamAdapter()

        assert (
            adapter.parse_event_payload(
                json.dumps(
                    {
                        "type": "message_start",
                        "message": {"id": "msg_1", "model": "claude-sonnet"},
                    }
                )
            )
            is None
        )

        chunk = adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "Hel"},
                }
            )
        )

        assert chunk is not None
        assert chunk.id == "msg_1"
        assert chunk.model == "claude-sonnet"
        assert chunk.choices[0].delta.content == "Hel"
        assert chunk.provider_extensions is not None
        assert chunk.provider_extensions["anthropic"]["event_kind"] == "text"

    def test_maps_tool_use_start_and_json_delta(self) -> None:
        """Stream adapter maps tool_use start and json argument deltas."""
        adapter = AnthropicMessagesStreamAdapter()

        adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "message_start",
                    "message": {"id": "msg_2", "model": "claude-sonnet"},
                }
            )
        )

        start_chunk = adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "content_block_start",
                    "index": 1,
                    "content_block": {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "lookup",
                        "input": {"city": "AMS"},
                    },
                }
            )
        )
        assert start_chunk is not None
        start_tool_calls = start_chunk.choices[0].delta.tool_calls
        assert start_tool_calls is not None
        assert start_tool_calls[0].id == "toolu_1"
        assert start_tool_calls[0].function.name == "lookup"
        assert start_chunk.provider_extensions is not None
        assert start_chunk.provider_extensions["anthropic"]["event_kind"] == "tool"

        delta_chunk = adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "content_block_delta",
                    "index": 1,
                    "delta": {"type": "input_json_delta", "partial_json": '{"c'},
                }
            )
        )
        assert delta_chunk is not None
        delta_tool_calls = delta_chunk.choices[0].delta.tool_calls
        assert delta_tool_calls is not None
        assert delta_tool_calls[0].id == "toolu_1"
        assert delta_tool_calls[0].function.arguments == '{"c'

    def test_maps_message_delta_and_message_stop(self) -> None:
        """Stream adapter maps stop reasons and message stop events."""
        adapter = AnthropicMessagesStreamAdapter()
        adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "message_start",
                    "message": {"id": "msg_3", "model": "claude-sonnet"},
                }
            )
        )

        stop_chunk = adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn"},
                }
            )
        )
        assert stop_chunk is not None
        assert stop_chunk.choices[0].finish_reason == "stop"

        message_stop_chunk = adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "message_stop",
                }
            )
        )
        assert message_stop_chunk is not None
        assert message_stop_chunk.choices[0].finish_reason == "stop"

    def test_maps_error_event(self) -> None:
        """Stream adapter maps error events to terminal error chunks."""
        adapter = AnthropicMessagesStreamAdapter()

        chunk = adapter.parse_event_payload('{"type": "error"}')

        assert chunk is not None
        assert chunk.choices[0].finish_reason == "error"
        assert chunk.provider_extensions is not None
        assert chunk.provider_extensions["anthropic"]["event_kind"] == "error"

    def test_returns_none_for_unhandled_or_invalid_shapes(self) -> None:
        """Stream adapter ignores unsupported events and malformed shapes."""
        adapter = AnthropicMessagesStreamAdapter()

        assert adapter.parse_event_payload('{"type":"ping"}') is None
        assert adapter.parse_event_payload('{"type": 1}') is None
        assert (
            adapter.parse_event_payload(
                '{"type":"content_block_start","index":0,"content_block":123}'
            )
            is None
        )
        assert (
            adapter.parse_event_payload(
                '{"type":"content_block_start","index":0,"content_block":{"type":"text"}}'
            )
            is None
        )
        start_chunk = adapter.parse_event_payload(
            '{"type":"content_block_start","index":0,"content_block":{"type":"tool_use","input":{}}}'
        )
        assert start_chunk is not None
        start_tool_calls = start_chunk.choices[0].delta.tool_calls
        assert start_tool_calls is not None
        assert start_tool_calls[0].function.name == "function"
        assert (
            adapter.parse_event_payload(
                '{"type":"content_block_delta","delta":{"type":"text_delta","text":123}}'
            )
            is None
        )
        assert (
            adapter.parse_event_payload(
                '{"type":"content_block_delta","delta":{"type":"input_json_delta","partial_json":123}}'
            )
            is None
        )
        assert (
            adapter.parse_event_payload(
                '{"type":"content_block_delta","delta":"invalid"}'
            )
            is None
        )
        assert (
            adapter.parse_event_payload(
                '{"type":"content_block_start","index":"1","content_block":{"type":"tool_use"}}'
            )
            is None
        )
        assert (
            adapter.parse_event_payload(
                '{"type":"content_block_delta","index":"x","delta":{"type":"input_json_delta","partial_json":"{"}}'
            )
            is None
        )
        assert (
            adapter.parse_event_payload(
                '{"type":"content_block_delta","delta":{"type":"other"}}'
            )
            is None
        )
        assert (
            adapter.parse_event_payload('{"type":"message_delta","delta":"invalid"}')
            is None
        )
        assert (
            adapter.parse_event_payload(
                '{"type":"message_delta","delta":{"stop_reason":null}}'
            )
            is None
        )

    def test_resets_tool_state_between_messages(self) -> None:
        """Stream adapter resets per-message tool state on message_start."""
        adapter = AnthropicMessagesStreamAdapter()

        adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "message_start",
                    "message": {"id": "msg_old", "model": "claude-sonnet"},
                }
            )
        )
        adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {
                        "type": "tool_use",
                        "id": "toolu_old",
                        "name": "lookup_old",
                        "input": {},
                    },
                }
            )
        )

        adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "message_start",
                    "message": {"id": "msg_new", "model": "claude-sonnet"},
                }
            )
        )

        chunk = adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "input_json_delta", "partial_json": "{"},
                }
            )
        )

        assert chunk is not None
        tool_calls = chunk.choices[0].delta.tool_calls
        assert tool_calls is not None
        assert tool_calls[0].id is None
        assert tool_calls[0].function.name == "function"

    def test_isolates_stream_state_per_execution_context(self) -> None:
        """Stream parser state stays isolated across independent contexts."""
        adapter = AnthropicMessagesStreamAdapter()

        first_context = copy_context()
        second_context = copy_context()

        first_context.run(
            adapter.parse_event_payload,
            json.dumps(
                {
                    "type": "message_start",
                    "message": {"id": "msg_ctx_a", "model": "claude-a"},
                }
            ),
        )
        second_context.run(
            adapter.parse_event_payload,
            json.dumps(
                {
                    "type": "message_start",
                    "message": {"id": "msg_ctx_b", "model": "claude-b"},
                }
            ),
        )

        chunk_a = first_context.run(
            adapter.parse_event_payload,
            json.dumps(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "A"},
                }
            ),
        )
        chunk_b = second_context.run(
            adapter.parse_event_payload,
            json.dumps(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "B"},
                }
            ),
        )

        assert chunk_a is not None
        assert chunk_b is not None
        assert chunk_a.id == "msg_ctx_a"
        assert chunk_b.id == "msg_ctx_b"
        assert chunk_a.model == "claude-a"
        assert chunk_b.model == "claude-b"

    def test_passthrough_for_choices_payload(self) -> None:
        """Stream adapter parses neutral choice payloads as passthrough chunks."""
        adapter = AnthropicMessagesStreamAdapter()

        chunk = adapter.parse_event_payload(
            '{"id":"raw_chunk","choices":[{"index":0,'
            '"delta":{"role":"assistant","content":"A"}}]}'
        )

        assert chunk is not None
        assert chunk.id == "raw_chunk"
        assert chunk.choices[0].delta.content == "A"

    def test_raises_value_error_for_invalid_json_and_non_object_payload(self) -> None:
        """Stream adapter rejects non-JSON and non-object payloads."""
        adapter = AnthropicMessagesStreamAdapter()

        with pytest.raises(ValueError):
            adapter.parse_event_payload("not-json")
        with pytest.raises(ValueError):
            adapter.parse_event_payload('"text"')


class TestAnthropicMessagesServiceIntegration:
    """Integration tests with LLMService and AsyncLLMService."""

    def test_sync_service_uses_adapters_for_non_streaming_responses(self) -> None:
        """LLMService can use Anthropic payload and response adapters together."""
        anthropic_payload = {
            "id": "msg_sync",
            "model": "claude-sonnet-4-20250514",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "OK"}],
        }
        transport = MockSyncTransport(content=_json_bytes(anthropic_payload))
        client = APIClient(base_url=_DUMMY_BASE_URL, transport=transport)
        service = LLMService(
            client,
            adapter_set=build_anthropic_messages_adapter_set(),
        )

        request = LLMGenerateRequest(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Ping"}],
        )
        completion = service.generate(request, path="/messages")

        sent = transport.send.call_args[0][0]
        body = json.loads(sent.content or b"{}")
        assert sent.url.endswith("/v1/llm/messages")
        assert body["model"] == "claude-sonnet-4-20250514"
        assert body["stream"] is False
        assert body["max_tokens"] == 1024
        assert completion.choices[0].message.content == "OK"

    def test_sync_service_defaults_max_tokens_when_option_has_no_max(self) -> None:
        """LLMService defaults max_tokens when options omit max_tokens."""
        anthropic_payload = {
            "id": "msg_sync_temp",
            "model": "claude-sonnet-4-20250514",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "OK"}],
        }
        transport = MockSyncTransport(content=_json_bytes(anthropic_payload))
        client = APIClient(base_url=_DUMMY_BASE_URL, transport=transport)
        service = LLMService(
            client,
            adapter_set=build_anthropic_messages_adapter_set(),
        )

        request = LLMGenerateRequest(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Ping"}],
            options=LLMExecutionOptions(temperature=0.1),
        )
        service.generate(request, path="/messages")

        sent = transport.send.call_args[0][0]
        body = json.loads(sent.content or b"{}")
        assert body["max_tokens"] == 1024

    async def test_async_service_uses_adapters_for_non_streaming_responses(
        self,
    ) -> None:
        """AsyncLLMService can use Anthropic payload and response adapters."""
        anthropic_payload = {
            "id": "msg_async",
            "model": "claude-sonnet-4-20250514",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "ASYNC"}],
        }
        transport = MockAsyncTransport(content=_json_bytes(anthropic_payload))
        client = AsyncAPIClient(base_url=_DUMMY_BASE_URL, transport=transport)
        service = AsyncLLMService(
            client,
            adapter_set=build_anthropic_messages_adapter_set(),
        )

        request = LLMGenerateRequest(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Ping"}],
        )
        completion = await service.generate(request, path="/messages")

        sent = transport.send.call_args[0][0]
        body = json.loads(sent.content or b"{}")
        assert sent.url.endswith("/v1/llm/messages")
        assert body["stream"] is False
        assert completion.choices[0].message.content == "ASYNC"

    def test_sync_service_uses_anthropic_stream_adapter(self) -> None:
        """LLMService parses Anthropic stream events with configured adapter."""
        transport = MockSyncTransport(content=b"")
        client = APIClient(base_url=_DUMMY_BASE_URL, transport=transport)
        service = LLMService(
            client,
            adapter_set=build_anthropic_messages_adapter_set(),
        )

        response = StreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=_SyncLineRaw(
                [
                    (
                        'data: {"type":"message_start","message":'
                        '{"id":"msg_s","model":"claude-sonnet"}}'
                    ),
                    (
                        'data: {"type":"content_block_delta","index":0,'
                        '"delta":{"type":"text_delta","text":"Hi"}}'
                    ),
                    'data: {"type":"message_stop"}',
                    "data: [DONE]",
                ]
            ),
        )

        chunks = list(service.iter_stream_chunks(response))

        assert [chunk.id for chunk in chunks] == ["msg_s", "msg_s"]
        assert chunks[0].choices[0].delta.content == "Hi"
        assert chunks[1].choices[0].finish_reason == "stop"
