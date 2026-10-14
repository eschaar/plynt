"""Tests for OpenAI adapter helpers and service integration."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

from plynt.base.response import StreamingResponse
from plynt.connectors.llm.adapters.openai import (
    OpenAIResponsesCompletionAdapter,
    OpenAIResponsesRequestAdapter,
    OpenAIResponsesStreamAdapter,
    _OpenAICompletionMapper,
    _OpenAIRequestMapper,
    _OpenAIStreamChunkFactory,
    _OpenAIStreamEventRouter,
    build_openai_responses_adapter_set,
)
from plynt.connectors.llm.models import (
    LLMExecutionOptions,
    LLMGenerateRequest,
    LLMMessage,
    LLMToolDefinition,
)
from plynt.connectors.llm.service import AsyncLLMService, LLMService
from plynt.http.client import APIClient, AsyncAPIClient
from tests.conftest import MockAsyncTransport, MockSyncTransport

_DUMMY_BASE_URL = "https://llm.example.com"


def _json_bytes(data: Any) -> bytes:
    """Render arbitrary payload to JSON bytes."""
    return json.dumps(data).encode("utf-8")


class _SyncLineRaw:
    """Simple sync stream stub yielding provided lines."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def iter_lines(self) -> Iterator[str]:
        return iter(self._lines)


class TestOpenAIResponsesPayloadAdapter:
    """Tests for request payload mapping."""

    def test_maps_neutral_request_to_openai_responses_shape(self) -> None:
        """Adapter maps core request fields to Responses payload fields."""
        adapter = OpenAIResponsesRequestAdapter()
        request = LLMGenerateRequest(
            model="gpt-5.5",
            messages=[{"role": "user", "content": "Hello"}],
            tools=[
                LLMToolDefinition(
                    name="get_weather",
                    description="Get weather",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "city": {"type": "string"},
                        },
                        "required": ["city"],
                        "additionalProperties": False,
                    },
                )
            ],
            tool_choice="auto",
            options=LLMExecutionOptions(
                temperature=0.2,
                max_tokens=256,
                top_p=0.9,
                metadata={"tenant": "acme"},
                provider_extensions={"store": False},
            ),
            provider_extensions={"reasoning": {"effort": "minimal"}},
        )

        payload = adapter.to_provider_payload(request, stream=False)

        assert payload["model"] == "gpt-5.5"
        assert payload["stream"] is False
        assert payload["input"] == [{"role": "user", "content": "Hello"}]
        assert payload["temperature"] == 0.2
        assert payload["max_output_tokens"] == 256
        assert payload["top_p"] == 0.9
        assert payload["metadata"] == {"tenant": "acme"}
        assert payload["store"] is False
        assert payload["reasoning"] == {"effort": "minimal"}
        assert payload["tool_choice"] == "auto"
        assert payload["tools"][0]["type"] == "function"
        assert payload["tools"][0]["name"] == "get_weather"

    def test_maps_typed_message_instances(self) -> None:
        """Adapter accepts typed LLMMessage objects in request messages."""
        adapter = OpenAIResponsesRequestAdapter()
        request = LLMGenerateRequest(
            messages=[LLMMessage(role="system", content="be brief")],
        )

        payload = adapter.to_provider_payload(request, stream=False)

        assert payload["input"] == [{"role": "system", "content": "be brief"}]


class TestOpenAIInternalMappers:
    """Tests for internal request/completion mapper behavior."""

    def test_request_mapper_handles_raw_dict_with_default_content(self) -> None:
        """Request mapper falls back to empty content for raw dict messages."""
        mapped = _OpenAIRequestMapper.message_to_input_item({"role": "user"})

        assert mapped == {"role": "user", "content": ""}

    def test_request_mapper_normalizes_invalid_dict_role_and_content(self) -> None:
        """Request mapper normalizes raw dict role/content to stable values."""
        mapped = _OpenAIRequestMapper.message_to_input_item(
            {"role": None, "content": None}
        )

        assert mapped == {"role": "user", "content": ""}

    def test_request_mapper_keeps_typed_multimodal_content_shape(self) -> None:
        """Request mapper preserves typed list content for multimodal messages."""
        message = LLMMessage(
            role="user",
            content=[{"type": "input_text", "text": "hello"}],
        )

        mapped = _OpenAIRequestMapper.message_to_input_item(message)

        assert mapped == {
            "role": "user",
            "content": [{"type": "input_text", "text": "hello"}],
        }

    def test_request_mapper_normalizes_non_dict_list_content_to_empty(self) -> None:
        """Request mapper drops non-dict list content blocks to empty content."""
        mapped = _OpenAIRequestMapper.message_to_input_item(
            {"role": "user", "content": ["text", 1, None]}
        )

        assert mapped == {"role": "user", "content": ""}

    def test_request_mapper_normalizes_scalar_content_to_string(self) -> None:
        """Request mapper converts scalar content values to stable strings."""
        mapped = _OpenAIRequestMapper.message_to_input_item(
            {"role": "user", "content": 123}
        )

        assert mapped == {"role": "user", "content": "123"}

    def test_request_mapper_tool_without_optional_fields(self) -> None:
        """Tool mapping keeps required fields when optional data is absent."""
        mapped = _OpenAIRequestMapper.tool_to_openai_function(
            LLMToolDefinition(name="lookup")
        )

        assert mapped == {"type": "function", "name": "lookup"}

    def test_completion_mapper_ignores_non_function_output_items(self) -> None:
        """Function tool-call extraction skips non-function output items."""
        tool_calls = _OpenAICompletionMapper.extract_function_tool_calls(
            [{"type": "message", "content": "no tool"}]
        )

        assert not tool_calls

    def test_classify_event_kind_returns_unknown_for_unmapped_event(self) -> None:
        """Event-kind classifier returns unknown for unsupported event types."""
        kind = _OpenAIStreamChunkFactory.classify_event_kind("response.unknown.custom")

        assert kind == "unknown"

    def test_router_parser_for_returns_parser_or_none(self) -> None:
        """Router lookup returns parser for known event and none otherwise."""
        assert _OpenAIStreamEventRouter.parser_for("response.created") is not None
        assert _OpenAIStreamEventRouter.parser_for("response.unknown.custom") is None


class TestOpenAIInternalStreamParsers:
    """Tests that validate parser behavior through the public stream adapter."""

    @staticmethod
    def _parse(payload: dict[str, Any]) -> Any:
        adapter = OpenAIResponsesStreamAdapter()
        return adapter.parse_event_payload(json.dumps(payload))

    def test_parse_created_event_keeps_top_level_response_fields(self) -> None:
        """Created-event parsing keeps top-level fields when no nested response."""
        chunk = self._parse(
            {
                "type": "response.created",
                "response_id": "resp_1",
                "model": "gpt-test",
            }
        )

        assert chunk is not None
        assert chunk.id == "resp_1"
        assert chunk.model == "gpt-test"

    def test_parse_output_item_event_handles_invalid_and_message_items(self) -> None:
        """Output-item parsing skips invalid items and maps message items."""
        assert self._parse({"type": "response.output_item.done", "item": None}) is None

        chunk = self._parse(
            {
                "type": "response.output_item.done",
                "response_id": "resp_msg",
                "item": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "hello"}],
                },
            }
        )

        assert chunk is not None
        assert chunk.choices[0].delta.content == "hello"
        assert (
            self._parse(
                {
                    "type": "response.output_item.done",
                    "response_id": "resp_unknown",
                    "item": {"type": "reasoning"},
                }
            )
            is None
        )

    def test_completion_mapper_skips_non_output_text_content_parts(self) -> None:
        """Completion mapper ignores content parts that are not output_text."""
        text = _OpenAICompletionMapper.extract_output_text(
            [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "other", "text": "x"},
                        {"type": "output_text", "text": "y"},
                    ],
                }
            ]
        )

        assert text == "y"

    def test_parse_refusal_delta_event_handles_valid_and_invalid_payload(self) -> None:
        """Refusal delta parsing maps strings and rejects invalid deltas."""
        chunk = self._parse(
            {
                "type": "response.refusal.delta",
                "response_id": "resp_refusal",
                "delta": "no",
            }
        )

        assert chunk is not None
        assert chunk.choices[0].delta.content == "no"
        assert self._parse({"type": "response.refusal.delta", "delta": 1}) is None

    def test_parse_function_done_event_rejects_non_function_items(self) -> None:
        """Function arguments done parsing returns none for non-function items."""
        chunk = self._parse(
            {
                "type": "response.function_call_arguments.done",
                "item": {"type": "message"},
            }
        )

        assert chunk is None

    def test_parse_function_done_event_without_item_uses_payload_fields(self) -> None:
        """Function arguments done parsing supports payload-level function fields."""
        chunk = self._parse(
            {
                "type": "response.function_call_arguments.done",
                "response_id": "resp_fn_done",
                "item_id": "item_fn_done",
                "name": "lookup",
                "arguments": "{}",
            }
        )

        assert chunk is not None
        tool_calls = chunk.choices[0].delta.tool_calls
        assert tool_calls is not None
        assert tool_calls[0].id == "item_fn_done"

    def test_parse_function_call_event_rejects_invalid_items(self) -> None:
        """Function-call parsing returns none for missing or non-function items."""
        assert self._parse({"type": "response.function_call.completed"}) is None
        assert (
            self._parse(
                {
                    "type": "response.function_call.completed",
                    "item": {"type": "message"},
                }
            )
            is None
        )

    def test_parse_function_call_event_maps_valid_function_item(self) -> None:
        """Function-call parsing maps valid function call lifecycle payloads."""
        chunk = self._parse(
            {
                "type": "response.function_call.completed",
                "response_id": "resp_fc",
                "item": {
                    "type": "function_call",
                    "id": "fc_1",
                    "call_id": "call_1",
                    "name": "lookup",
                    "arguments": "{}",
                },
            }
        )

        assert chunk is not None
        tool_calls = chunk.choices[0].delta.tool_calls
        assert tool_calls is not None
        assert tool_calls[0].function.name == "lookup"

    def test_parse_annotation_content_and_tool_events(self) -> None:
        """Annotation/content/tool events map to empty content chunks."""
        annotation = self._parse(
            {
                "type": "response.output_text.annotation.added",
                "response_id": "resp_ann",
            }
        )
        content_part = self._parse(
            {
                "type": "response.content_part.done",
                "response_id": "resp_part",
            }
        )
        tool = self._parse(
            {
                "type": "response.web_search_call.in_progress",
                "response_id": "resp_tool",
            }
        )

        assert annotation is not None
        assert content_part is not None
        assert tool is not None
        assert annotation.choices[0].delta.content == ""
        assert content_part.choices[0].delta.content == ""
        assert tool.choices[0].delta.content == ""

    @pytest.mark.parametrize(
        ("payload", "expected_finish", "expected_content"),
        [
            (
                {
                    "type": "response.refusal.done",
                    "response_id": "r1",
                    "refusal": "cannot",
                },
                None,
                "cannot",
            ),
            (
                {
                    "type": "response.reasoning_text.delta",
                    "response_id": "r2",
                    "delta": "think",
                },
                None,
                "think",
            ),
            (
                {
                    "type": "response.reasoning_text.done",
                    "response_id": "r3",
                    "text": "done",
                },
                None,
                "done",
            ),
            (
                {
                    "type": "response.reasoning_summary_text.delta",
                    "response_id": "r4",
                    "delta": "sum",
                },
                None,
                "sum",
            ),
            (
                {
                    "type": "response.reasoning_summary_text.done",
                    "response_id": "r5",
                    "text": "summary",
                },
                None,
                "summary",
            ),
            (
                {
                    "type": "response.audio.delta",
                    "response_id": "r6",
                    "delta": "pcm",
                },
                None,
                "pcm",
            ),
            ({"type": "response.audio.done", "response_id": "r7"}, None, ""),
            (
                {
                    "type": "response.audio.transcript.delta",
                    "response_id": "r8",
                    "delta": "transcript-part",
                },
                None,
                "transcript-part",
            ),
            (
                {
                    "type": "response.audio.transcript.done",
                    "response_id": "r9",
                    "transcript": "full transcript",
                },
                None,
                "full transcript",
            ),
            (
                {
                    "type": "response.created",
                    "response": {
                        "id": "r10",
                        "model": "gpt-x",
                        "status": "in_progress",
                    },
                },
                None,
                "",
            ),
            ({"type": "response.in_progress", "response_id": "r11"}, None, ""),
            ({"type": "response.queued", "response_id": "r12"}, None, ""),
            (
                {"type": "response.cancelled", "response_id": "r13"},
                "error",
                "",
            ),
            (
                {"type": "response.incomplete", "response_id": "r14"},
                "error",
                "",
            ),
            ({"type": "error", "response_id": "r15"}, "error", ""),
        ],
    )
    def test_parser_methods_map_supported_event_variants(
        self,
        payload: dict[str, Any],
        expected_finish: str | None,
        expected_content: str,
    ) -> None:
        """Adapter maps supported event variants to expected chunks."""
        chunk = self._parse(payload)

        assert chunk is not None
        assert chunk.choices[0].delta.content == expected_content
        assert chunk.choices[0].finish_reason == expected_finish

    @pytest.mark.parametrize(
        "payload",
        [
            {"type": "response.refusal.done", "refusal": 1},
            {"type": "response.reasoning_text.delta", "delta": 1},
            {"type": "response.reasoning_text.done", "text": 1},
            {"type": "response.reasoning_summary_text.delta", "delta": 1},
            {"type": "response.reasoning_summary_text.done", "text": 1},
            {"type": "response.audio.delta", "delta": 1},
            {"type": "response.audio.transcript.delta", "delta": 1},
            {"type": "response.audio.transcript.done", "transcript": 1},
        ],
    )
    def test_parser_methods_return_none_for_invalid_value_shapes(
        self,
        payload: dict[str, Any],
    ) -> None:
        """Adapter returns none for unsupported value shapes."""
        assert self._parse(payload) is None

    def test_stream_chunk_factory_rejects_non_string_arguments(self) -> None:
        """Function chunk factory rejects non-string function arguments."""
        chunk = _OpenAIStreamChunkFactory.build_function_chunk_from_parts(
            {"response_id": "r_bad"},
            name="tool",
            arguments={"a": 1},
            call_id="call_bad",
            event_type="response.function_call_arguments.delta",
        )

        assert chunk is None


class TestOpenAIResponsesCompletionAdapter:
    """Tests for response normalization."""

    def test_maps_output_message_text_to_completion_payload(self) -> None:
        """Adapter maps assistant output text into neutral choices payload."""
        adapter = OpenAIResponsesCompletionAdapter()
        raw = {
            "id": "resp_123",
            "model": "gpt-5.5",
            "status": "completed",
            "usage": {
                "input_tokens": 5,
                "output_tokens": 7,
                "total_tokens": 12,
            },
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": "Hello"},
                        {"type": "output_text", "text": " world"},
                    ],
                }
            ],
        }

        normalized = adapter.to_neutral_completion_payload(raw)

        assert normalized["id"] == "resp_123"
        assert normalized["choices"][0]["message"]["role"] == "assistant"
        assert normalized["choices"][0]["message"]["content"] == "Hello world"
        assert normalized["choices"][0]["finish_reason"] == "stop"
        assert normalized["usage"]["total_tokens"] == 12
        assert normalized["provider_extensions"]["openai"]["event_kind"] == "completion"

    def test_maps_string_message_content(self) -> None:
        """Adapter supports provider output items with plain string content."""
        adapter = OpenAIResponsesCompletionAdapter()
        raw = {
            "id": "resp_string",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": "plain text",
                }
            ],
        }

        normalized = adapter.to_neutral_completion_payload(raw)

        assert normalized["choices"][0]["message"]["content"] == "plain text"

    def test_ignores_non_list_and_non_dict_message_parts(self) -> None:
        """Adapter skips malformed message content items safely."""
        adapter = OpenAIResponsesCompletionAdapter()
        raw = {
            "id": "resp_malformed",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "ok"}, 123],
                },
                {
                    "type": "message",
                    "role": "assistant",
                    "content": {"bad": "shape"},
                },
            ],
        }

        normalized = adapter.to_neutral_completion_payload(raw)

        assert normalized["choices"][0]["message"]["content"] == "ok"

    def test_maps_function_call_items_to_tool_calls(self) -> None:
        """Adapter maps function_call output items to neutral tool_calls."""
        adapter = OpenAIResponsesCompletionAdapter()
        raw = {
            "id": "resp_456",
            "model": "gpt-5.5",
            "status": "completed",
            "output": [
                {
                    "type": "function_call",
                    "id": "fc_1",
                    "call_id": "call_1",
                    "name": "get_weather",
                    "arguments": '{"city":"Amsterdam"}',
                }
            ],
        }

        normalized = adapter.to_neutral_completion_payload(raw)
        tool_calls = normalized["choices"][0]["message"]["tool_calls"]

        assert len(tool_calls) == 1
        assert tool_calls[0]["id"] == "call_1"
        assert tool_calls[0]["function"]["name"] == "get_weather"

    def test_ignores_function_calls_without_name(self) -> None:
        """Adapter skips function_call output items that have no valid name."""
        adapter = OpenAIResponsesCompletionAdapter()
        raw = {
            "id": "resp_bad_call",
            "status": "completed",
            "output": [
                {
                    "type": "function_call",
                    "arguments": "{}",
                }
            ],
        }

        normalized = adapter.to_neutral_completion_payload(raw)

        assert "tool_calls" not in normalized["choices"][0]["message"]

    def test_defaults_function_call_arguments_when_not_string(self) -> None:
        """Adapter falls back to empty JSON object for non-string arguments."""
        adapter = OpenAIResponsesCompletionAdapter()
        raw = {
            "id": "resp_arg_fallback",
            "status": "completed",
            "output": [
                {
                    "type": "function_call",
                    "name": "lookup",
                    "arguments": {"bad": "shape"},
                }
            ],
        }

        normalized = adapter.to_neutral_completion_payload(raw)
        tool_calls = normalized["choices"][0]["message"]["tool_calls"]

        assert tool_calls[0]["function"]["arguments"] == "{}"


class TestOpenAIResponsesStreamAdapter:
    """Tests for stream-event normalization."""

    def test_maps_output_text_delta_event(self) -> None:
        """Stream adapter maps text delta events into neutral chunks."""
        adapter = OpenAIResponsesStreamAdapter()

        chunk = adapter.parse_event_payload(
            '{"type":"response.output_text.delta","response_id":"resp_1",'
            '"output_index":0,"delta":"Hel"}'
        )

        assert chunk is not None
        assert chunk.id == "resp_1"
        assert chunk.choices[0].delta.content == "Hel"
        assert chunk.provider_extensions is not None
        assert (
            chunk.provider_extensions["openai"]["event_type"]
            == "response.output_text.delta"
        )
        assert chunk.provider_extensions["openai"]["event_kind"] == "text"

    def test_maps_function_arguments_delta_event(self) -> None:
        """Stream adapter maps function argument deltas to tool call chunks."""
        adapter = OpenAIResponsesStreamAdapter()

        chunk = adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "response.function_call_arguments.delta",
                    "response_id": "resp_2",
                    "output_index": 0,
                    "call_id": "call_1",
                    "name": "lookup",
                    "delta": '{"id":1}',
                }
            )
        )

        assert chunk is not None
        tool_calls = chunk.choices[0].delta.tool_calls
        assert tool_calls is not None
        assert tool_calls[0].id == "call_1"
        assert tool_calls[0].function.name == "lookup"
        assert tool_calls[0].function.arguments == '{"id":1}'

    def test_maps_function_arguments_done_event(self) -> None:
        """Stream adapter maps function argument done events to tool calls."""
        adapter = OpenAIResponsesStreamAdapter()

        chunk = adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "response.function_call_arguments.done",
                    "response_id": "resp_2_done",
                    "output_index": 0,
                    "item": {
                        "type": "function_call",
                        "id": "fc_done_1",
                        "call_id": "call_done_1",
                        "name": "lookup_done",
                        "arguments": '{"id":2}',
                    },
                }
            )
        )

        assert chunk is not None
        tool_calls = chunk.choices[0].delta.tool_calls
        assert tool_calls is not None
        assert tool_calls[0].id == "call_done_1"
        assert tool_calls[0].function.name == "lookup_done"
        assert tool_calls[0].function.arguments == '{"id":2}'

    def test_maps_output_item_added_function_call_event(self) -> None:
        """Stream adapter maps output item events carrying function calls."""
        adapter = OpenAIResponsesStreamAdapter()

        chunk = adapter.parse_event_payload(
            json.dumps(
                {
                    "type": "response.output_item.added",
                    "response_id": "resp_item_1",
                    "output_index": 0,
                    "item": {
                        "type": "function_call",
                        "id": "fc_item_1",
                        "call_id": "call_item_1",
                        "name": "search_docs",
                        "arguments": "{}",
                    },
                }
            )
        )

        assert chunk is not None
        tool_calls = chunk.choices[0].delta.tool_calls
        assert tool_calls is not None
        assert tool_calls[0].id == "call_item_1"
        assert tool_calls[0].function.name == "search_docs"

    def test_maps_generic_error_event(self) -> None:
        """Stream adapter maps generic error events to error finish reason."""
        adapter = OpenAIResponsesStreamAdapter()

        chunk = adapter.parse_event_payload('{"type":"error","response_id":"resp_e"}')

        assert chunk is not None
        assert chunk.choices[0].finish_reason == "error"
        assert chunk.provider_extensions is not None
        assert chunk.provider_extensions["openai"]["event_kind"] == "error"

    def test_maps_completed_event_to_stop_reason(self) -> None:
        """Stream adapter maps completed response event to stop finish reason."""
        adapter = OpenAIResponsesStreamAdapter()

        chunk = adapter.parse_event_payload(
            '{"type":"response.completed","response_id":"resp_3"}'
        )

        assert chunk is not None
        assert chunk.choices[0].finish_reason == "stop"
        assert chunk.provider_extensions is not None
        assert chunk.provider_extensions["openai"]["event_kind"] == "lifecycle"

    def test_maps_output_text_done_event(self) -> None:
        """Stream adapter maps output_text.done events."""
        adapter = OpenAIResponsesStreamAdapter()

        chunk = adapter.parse_event_payload(
            '{"type":"response.output_text.done","response_id":"resp_done",'
            '"text":"Hello"}'
        )

        assert chunk is not None
        assert chunk.choices[0].delta.content == "Hello"

    def test_maps_failed_event_to_error_finish_reason(self) -> None:
        """Stream adapter maps failed events to error finish reason."""
        adapter = OpenAIResponsesStreamAdapter()

        chunk = adapter.parse_event_payload(
            '{"type":"response.failed","response_id":"resp_fail"}'
        )

        assert chunk is not None
        assert chunk.choices[0].finish_reason == "error"

    def test_maps_function_delta_with_default_name(self) -> None:
        """Stream adapter uses fallback function name when name is absent."""
        adapter = OpenAIResponsesStreamAdapter()

        chunk = adapter.parse_event_payload(
            '{"type":"response.function_call_arguments.delta",'
            '"response_id":"resp_fn","item_id":"item_1","delta":"{}"}'
        )

        assert chunk is not None
        tool_calls = chunk.choices[0].delta.tool_calls
        assert tool_calls is not None
        assert tool_calls[0].id == "item_1"
        assert tool_calls[0].function.name == "function"

    def test_returns_none_for_invalid_stream_payload_shapes(self) -> None:
        """Stream adapter returns none for events with invalid value shapes."""
        adapter = OpenAIResponsesStreamAdapter()

        assert (
            adapter.parse_event_payload(
                '{"type":"response.output_text.delta","delta":123}'
            )
            is None
        )
        assert (
            adapter.parse_event_payload(
                '{"type":"response.output_text.done","text":123}'
            )
            is None
        )
        assert (
            adapter.parse_event_payload(
                '{"type":"response.function_call_arguments.delta","delta":123}'
            )
            is None
        )

    def test_raises_value_error_for_invalid_json_and_non_object_payload(self) -> None:
        """Stream adapter rejects non-JSON and non-object stream payloads."""
        adapter = OpenAIResponsesStreamAdapter()

        with pytest.raises(ValueError):
            adapter.parse_event_payload("not-json")
        with pytest.raises(ValueError):
            adapter.parse_event_payload('"text"')

    def test_passthrough_for_choices_payload(self) -> None:
        """Stream adapter parses neutral choices payloads as passthrough chunks."""
        adapter = OpenAIResponsesStreamAdapter()

        chunk = adapter.parse_event_payload(
            '{"id":"raw_chunk","choices":[{"index":0,'
            '"delta":{"role":"assistant","content":"A"}}]}'
        )

        assert chunk is not None
        assert chunk.id == "raw_chunk"
        assert chunk.choices[0].delta.content == "A"

    def test_returns_none_when_type_field_missing_or_not_string(self) -> None:
        """Stream adapter ignores event objects without a valid type field."""
        adapter = OpenAIResponsesStreamAdapter()

        assert adapter.parse_event_payload('{"response_id":"resp_x"}') is None
        assert adapter.parse_event_payload('{"type":1,"response_id":"resp_x"}') is None

    def test_ignores_unhandled_event_types(self) -> None:
        """Stream adapter returns none for unsupported OpenAI stream events."""
        adapter = OpenAIResponsesStreamAdapter()

        chunk = adapter.parse_event_payload(
            '{"type":"response.unknown","response_id":"resp_4"}'
        )

        assert chunk is None


class TestOpenAIResponsesServiceIntegration:
    """Integration tests with LLMService and AsyncLLMService."""

    def test_sync_service_uses_adapters_for_non_streaming_responses(self) -> None:
        """LLMService can use OpenAI payload and response adapters together."""
        openai_payload = {
            "id": "resp_sync",
            "model": "gpt-5.5",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "OK"}],
                }
            ],
        }
        transport = MockSyncTransport(content=_json_bytes(openai_payload))
        client = APIClient(base_url=_DUMMY_BASE_URL, transport=transport)
        service = LLMService(
            client,
            adapter_set=build_openai_responses_adapter_set(),
        )

        request = LLMGenerateRequest(
            model="gpt-5.5",
            messages=[{"role": "user", "content": "Ping"}],
        )
        completion = service.generate(request, path="/responses")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/v1/llm/responses")
        assert json.loads(sent.content or b"{}") == {
            "model": "gpt-5.5",
            "input": [{"role": "user", "content": "Ping"}],
            "stream": False,
        }
        assert completion.choices[0].message.content == "OK"

    async def test_async_service_uses_adapters_for_non_streaming_responses(
        self,
    ) -> None:
        """AsyncLLMService can use OpenAI payload and response adapters together."""
        openai_payload = {
            "id": "resp_async",
            "model": "gpt-5.5",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "ASYNC"}],
                }
            ],
        }
        transport = MockAsyncTransport(content=_json_bytes(openai_payload))
        client = AsyncAPIClient(base_url=_DUMMY_BASE_URL, transport=transport)
        service = AsyncLLMService(
            client,
            adapter_set=build_openai_responses_adapter_set(),
        )

        request = LLMGenerateRequest(
            model="gpt-5.5",
            messages=[{"role": "user", "content": "Ping"}],
        )
        completion = await service.generate(request, path="/responses")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/v1/llm/responses")
        assert json.loads(sent.content or b"{}") == {
            "model": "gpt-5.5",
            "input": [{"role": "user", "content": "Ping"}],
            "stream": False,
        }
        assert completion.choices[0].message.content == "ASYNC"

    def test_sync_service_uses_openai_stream_adapter(self) -> None:
        """LLMService parses OpenAI stream events when adapter set is configured."""
        transport = MockSyncTransport(content=b"")
        client = APIClient(base_url=_DUMMY_BASE_URL, transport=transport)
        service = LLMService(
            client,
            adapter_set=build_openai_responses_adapter_set(),
        )

        response = StreamingResponse(
            status_code=200,
            headers={},
            content=b"",
            _raw=_SyncLineRaw(
                [
                    'data: {"type":"response.output_text.delta",'
                    '"response_id":"resp_s","output_index":0,"delta":"Hi"}',
                    'data: {"type":"response.completed","response_id":"resp_s"}',
                    "data: [DONE]",
                ]
            ),
        )

        chunks = list(service.iter_stream_chunks(response))

        assert [chunk.id for chunk in chunks] == ["resp_s", "resp_s"]
        assert chunks[0].choices[0].delta.content == "Hi"
        assert chunks[1].choices[0].finish_reason == "stop"
