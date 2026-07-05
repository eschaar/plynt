"""OpenAI adapter implementations for ``plynth.connectors.llm``."""

from __future__ import annotations

import json
from collections.abc import Callable
from json import JSONDecodeError
from typing import Any

from plynth.connectors.llm.adapters.base import (
    DefaultLLMCompletionAdapter,
    DefaultLLMStreamAdapter,
    LLMAdapterSet,
    LLMRequestAdapter,
)
from plynth.connectors.llm.models import (
    LLMGenerateRequest,
    LLMMessage,
    LLMStreamChunk,
    LLMToolDefinition,
)


def _message_to_input_item(message: LLMMessage | dict[str, Any]) -> dict[str, Any]:
    """Convert one neutral message to a Responses API input item."""
    if isinstance(message, dict):
        role = str(message.get("role", "user"))
        content = message.get("content", "")
        return {"role": role, "content": content}

    return {"role": message.role, "content": message.content or ""}


def _tool_to_openai_function(tool: LLMToolDefinition) -> dict[str, Any]:
    """Convert one neutral tool definition to OpenAI function-tool format."""
    payload: dict[str, Any] = {
        "type": "function",
        "name": tool.name,
    }
    if tool.description is not None:
        payload["description"] = tool.description
    if tool.input_schema is not None:
        payload["parameters"] = tool.input_schema
    return payload


def _apply_request_options(
    payload: dict[str, Any],
    request: LLMGenerateRequest,
) -> None:
    """Apply neutral execution options onto an OpenAI payload."""
    if request.options is None:
        return

    if request.options.temperature is not None:
        payload["temperature"] = request.options.temperature
    if request.options.max_tokens is not None:
        payload["max_output_tokens"] = request.options.max_tokens
    if request.options.top_p is not None:
        payload["top_p"] = request.options.top_p
    if request.options.metadata is not None:
        payload["metadata"] = request.options.metadata

    if request.options.provider_extensions is not None:
        payload.update(request.options.provider_extensions)


class OpenAIResponsesRequestAdapter(LLMRequestAdapter):
    """Map neutral requests to OpenAI Responses payloads."""

    def to_provider_payload(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Build provider payload for the OpenAI Responses API."""
        payload: dict[str, Any] = {
            "input": [_message_to_input_item(message) for message in request.messages],
            "stream": stream,
        }

        if request.model is not None:
            payload["model"] = request.model

        if request.tools:
            payload["tools"] = [
                _tool_to_openai_function(tool) for tool in request.tools
            ]

        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice

        _apply_request_options(payload, request)

        if request.provider_extensions is not None:
            payload.update(request.provider_extensions)

        return payload


def _extract_output_text(output_items: list[dict[str, Any]]) -> str:
    """Extract concatenated assistant text from OpenAI output items."""
    chunks: list[str] = []

    for item in output_items:
        if item.get("type") != "message" or item.get("role") != "assistant":
            continue

        content = item.get("content")
        if isinstance(content, str):
            chunks.append(content)
            continue

        if not isinstance(content, list):
            continue

        for part in content:
            if not isinstance(part, dict):
                continue

            if part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)

    return "".join(chunks)


def _extract_function_tool_calls(
    output_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract function call items to neutral ``tool_calls`` shape."""
    tool_calls: list[dict[str, Any]] = []

    for item in output_items:
        if item.get("type") != "function_call":
            continue

        name = item.get("name")
        arguments = item.get("arguments")
        if not isinstance(name, str):
            continue
        if not isinstance(arguments, str):
            arguments = "{}"

        tool_calls.append(
            {
                "id": item.get("call_id") or item.get("id"),
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": arguments,
                },
            }
        )

    return tool_calls


class OpenAIResponsesCompletionAdapter(DefaultLLMCompletionAdapter):
    """Map OpenAI Responses completion payloads to neutral completions."""

    def to_neutral_completion_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Map provider payload into neutral completion shape."""
        raw_output = payload.get("output")
        output_items: list[dict[str, Any]] = (
            [item for item in raw_output if isinstance(item, dict)]
            if isinstance(raw_output, list)
            else []
        )

        message: dict[str, Any] = {
            "role": "assistant",
            "content": _extract_output_text(output_items),
        }

        tool_calls = _extract_function_tool_calls(output_items)
        if tool_calls:
            message["tool_calls"] = tool_calls

        finish_reason = "stop" if payload.get("status") == "completed" else None

        return {
            "id": payload.get("id"),
            "model": payload.get("model"),
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": finish_reason,
                }
            ],
            "usage": payload.get("usage"),
            "provider_extensions": {
                "openai": {
                    "response_status": payload.get("status"),
                }
            },
        }


def _build_text_stream_chunk(
    payload: dict[str, Any],
    *,
    content: str,
    event_type: str,
    finish_reason: str | None = None,
) -> LLMStreamChunk:
    """Build one neutral text delta chunk from an OpenAI stream event."""
    return LLMStreamChunk.from_payload(
        {
            "id": payload.get("response_id") or payload.get("id"),
            "model": payload.get("model"),
            "choices": [
                {
                    "index": payload.get("output_index", 0),
                    "delta": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": finish_reason,
                }
            ],
            "provider_extensions": {
                "openai": {
                    "event_type": event_type,
                    "status": payload.get("status"),
                }
            },
        }
    )


def _build_function_stream_chunk(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Build one neutral tool-call delta chunk from an OpenAI stream event."""
    arguments = payload.get("delta")
    if not isinstance(arguments, str):
        return None

    name = payload.get("name")
    if not isinstance(name, str) or not name:
        name = "function"

    call_id = payload.get("call_id") or payload.get("item_id")

    return LLMStreamChunk.from_payload(
        _function_stream_chunk_payload(
            payload,
            name=name,
            arguments=arguments,
            call_id=call_id,
            event_type="response.function_call_arguments.delta",
        )
    )


def _function_stream_chunk_payload(
    payload: dict[str, Any],
    *,
    name: str,
    arguments: str,
    call_id: str | None,
    event_type: str,
) -> dict[str, Any]:
    """Build one neutral function-call stream payload."""
    return {
        "id": payload.get("response_id") or payload.get("id"),
        "model": payload.get("model"),
        "choices": [
            {
                "index": payload.get("output_index", 0),
                "delta": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": arguments,
                            },
                        }
                    ],
                },
                "finish_reason": None,
            }
        ],
        "provider_extensions": {
            "openai": {
                "event_type": event_type,
            }
        },
    }


def _build_function_stream_chunk_from_parts(
    payload: dict[str, Any],
    *,
    name: Any,
    arguments: Any,
    call_id: Any,
    event_type: str,
) -> LLMStreamChunk | None:
    """Build one neutral tool-call chunk from parsed function call fields."""
    if not isinstance(arguments, str):
        return None

    normalized_name = name if isinstance(name, str) and name else "function"
    normalized_call_id = call_id if isinstance(call_id, str) else None

    return LLMStreamChunk.from_payload(
        _function_stream_chunk_payload(
            payload,
            name=normalized_name,
            arguments=arguments,
            call_id=normalized_call_id,
            event_type=event_type,
        )
    )


def _parse_function_arguments_done_event(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse ``response.function_call_arguments.done`` events."""
    item = payload.get("item")
    if isinstance(item, dict):
        if item.get("type") != "function_call":
            return None
        return _build_function_stream_chunk_from_parts(
            payload,
            name=item.get("name"),
            arguments=item.get("arguments"),
            call_id=item.get("call_id") or item.get("id"),
            event_type="response.function_call_arguments.done",
        )

    return _build_function_stream_chunk_from_parts(
        payload,
        name=payload.get("name"),
        arguments=payload.get("arguments"),
        call_id=payload.get("call_id") or payload.get("item_id"),
        event_type="response.function_call_arguments.done",
    )


def _parse_output_item_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse ``response.output_item.added`` and ``response.output_item.done``."""
    item = payload.get("item")
    if not isinstance(item, dict):
        return None

    event_type = str(payload.get("type", "response.output_item.added"))
    item_type = item.get("type")
    if item_type == "function_call":
        return _build_function_stream_chunk_from_parts(
            payload,
            name=item.get("name"),
            arguments=item.get("arguments"),
            call_id=item.get("call_id") or item.get("id"),
            event_type=event_type,
        )

    if item_type == "message":
        text = _extract_output_text([item])
        return _build_text_stream_chunk(
            payload,
            content=text,
            event_type=event_type,
        )

    return None


def _parse_text_delta_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse ``response.text.delta`` events as output text deltas."""
    delta = payload.get("delta")
    if not isinstance(delta, str):
        return None
    return _build_text_stream_chunk(
        payload,
        content=delta,
        event_type="response.text.delta",
    )


def _parse_text_done_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse ``response.text.done`` events as output text done chunks."""
    text = payload.get("text")
    if not isinstance(text, str):
        return None
    return _build_text_stream_chunk(
        payload,
        content=text,
        event_type="response.text.done",
    )


def _parse_error_event(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse ``error`` events to terminal error chunks."""
    return _build_text_stream_chunk(
        payload,
        content="",
        event_type="error",
        finish_reason="error",
    )


def _parse_in_progress_event(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse ``response.in_progress`` lifecycle events."""
    return _build_text_stream_chunk(
        payload,
        content="",
        event_type="response.in_progress",
        finish_reason=None,
    )


def _parse_created_event(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse ``response.created`` lifecycle events."""
    return _build_text_stream_chunk(
        payload,
        content="",
        event_type="response.created",
        finish_reason=None,
    )


def _parse_response_object_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse events that embed a ``response`` object."""
    response = payload.get("response")
    if not isinstance(response, dict):
        return None

    merged_payload = {
        **payload,
        "response_id": response.get("id") or payload.get("response_id"),
        "model": response.get("model") or payload.get("model"),
        "status": response.get("status") or payload.get("status"),
    }
    return _build_text_stream_chunk(
        merged_payload,
        content="",
        event_type=str(payload.get("type", "response.created")),
        finish_reason=None,
    )


def _parse_output_item_lifecycle_event(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse output item lifecycle events into lightweight status chunks."""
    return _build_text_stream_chunk(
        payload,
        content="",
        event_type=str(payload.get("type", "response.output_item.added")),
        finish_reason=None,
    )


def _parse_content_part_event(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse content part lifecycle events into lightweight status chunks."""
    return _build_text_stream_chunk(
        payload,
        content="",
        event_type=str(payload.get("type", "response.content_part.added")),
        finish_reason=None,
    )


def _parse_refusal_delta_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse ``response.refusal.delta`` as assistant content deltas."""
    delta = payload.get("delta")
    if not isinstance(delta, str):
        return None
    return _build_text_stream_chunk(
        payload,
        content=delta,
        event_type="response.refusal.delta",
    )


def _parse_refusal_done_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse ``response.refusal.done`` as assistant content chunks."""
    refusal = payload.get("refusal")
    if not isinstance(refusal, str):
        return None
    return _build_text_stream_chunk(
        payload,
        content=refusal,
        event_type="response.refusal.done",
    )


def _parse_reasoning_text_delta_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse reasoning text delta events as assistant content deltas."""
    delta = payload.get("delta")
    if not isinstance(delta, str):
        return None
    return _build_text_stream_chunk(
        payload,
        content=delta,
        event_type="response.reasoning_text.delta",
    )


def _parse_reasoning_text_done_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse reasoning text done events as assistant content chunks."""
    text = payload.get("text")
    if not isinstance(text, str):
        return None
    return _build_text_stream_chunk(
        payload,
        content=text,
        event_type="response.reasoning_text.done",
    )


def _parse_summary_text_delta_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse reasoning summary text delta events."""
    delta = payload.get("delta")
    if not isinstance(delta, str):
        return None
    return _build_text_stream_chunk(
        payload,
        content=delta,
        event_type="response.reasoning_summary_text.delta",
    )


def _parse_summary_text_done_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse reasoning summary text done events."""
    text = payload.get("text")
    if not isinstance(text, str):
        return None
    return _build_text_stream_chunk(
        payload,
        content=text,
        event_type="response.reasoning_summary_text.done",
    )


def _parse_annotation_event(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse output text annotation added events."""
    return _build_text_stream_chunk(
        payload,
        content="",
        event_type="response.output_text.annotation.added",
        finish_reason=None,
    )


def _parse_function_call_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse function call lifecycle events that carry a full item object."""
    item = payload.get("item")
    if not isinstance(item, dict):
        return None
    if item.get("type") != "function_call":
        return None

    return _build_function_stream_chunk_from_parts(
        payload,
        name=item.get("name"),
        arguments=item.get("arguments"),
        call_id=item.get("call_id") or item.get("id"),
        event_type=str(payload.get("type", "response.function_call.done")),
    )


def _parse_tool_event(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse tool status events as lightweight assistant chunks."""
    return _build_text_stream_chunk(
        payload,
        content="",
        event_type=str(payload.get("type", "response.tool.in_progress")),
        finish_reason=None,
    )


def _parse_audio_delta_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse audio delta events into assistant content chunks."""
    delta = payload.get("delta")
    if not isinstance(delta, str):
        return None
    return _build_text_stream_chunk(
        payload,
        content=delta,
        event_type="response.audio.delta",
        finish_reason=None,
    )


def _parse_audio_done_event(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse audio done events as lightweight completion markers."""
    return _build_text_stream_chunk(
        payload,
        content="",
        event_type="response.audio.done",
        finish_reason=None,
    )


def _parse_audio_transcript_delta_event(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse audio transcript delta events to assistant content chunks."""
    delta = payload.get("delta")
    if not isinstance(delta, str):
        return None
    return _build_text_stream_chunk(
        payload,
        content=delta,
        event_type="response.audio.transcript.delta",
        finish_reason=None,
    )


def _parse_audio_transcript_done_event(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse audio transcript done events to assistant content chunks."""
    transcript = payload.get("transcript")
    if not isinstance(transcript, str):
        return None
    return _build_text_stream_chunk(
        payload,
        content=transcript,
        event_type="response.audio.transcript.done",
        finish_reason=None,
    )


def _parse_queued_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse ``response.queued`` events."""
    return _parse_response_object_event(payload)


def _parse_incomplete_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse ``response.incomplete`` events."""
    response = payload.get("response")
    if isinstance(response, dict):
        merged_payload = {
            **payload,
            "response_id": response.get("id") or payload.get("response_id"),
            "model": response.get("model") or payload.get("model"),
            "status": response.get("status") or payload.get("status"),
        }
        return _build_text_stream_chunk(
            merged_payload,
            content="",
            event_type="response.incomplete",
            finish_reason="error",
        )

    return _build_text_stream_chunk(
        payload,
        content="",
        event_type="response.incomplete",
        finish_reason="error",
    )


def _parse_cancelled_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse ``response.cancelled`` events."""
    response = payload.get("response")
    if isinstance(response, dict):
        merged_payload = {
            **payload,
            "response_id": response.get("id") or payload.get("response_id"),
            "model": response.get("model") or payload.get("model"),
            "status": response.get("status") or payload.get("status"),
        }
        return _build_text_stream_chunk(
            merged_payload,
            content="",
            event_type="response.cancelled",
            finish_reason="error",
        )

    return _build_text_stream_chunk(
        payload,
        content="",
        event_type="response.cancelled",
        finish_reason="error",
    )


def _parse_failed_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse ``response.failed`` events."""
    response = payload.get("response")
    if isinstance(response, dict):
        merged_payload = {
            **payload,
            "response_id": response.get("id") or payload.get("response_id"),
            "model": response.get("model") or payload.get("model"),
            "status": response.get("status") or payload.get("status"),
        }
        return _build_text_stream_chunk(
            merged_payload,
            content="",
            event_type="response.failed",
            finish_reason="error",
        )

    return _build_text_stream_chunk(
        payload,
        content="",
        event_type="response.failed",
        finish_reason="error",
    )


def _parse_completed_event_with_response(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse ``response.completed`` events that may embed a response object."""
    response = payload.get("response")
    if isinstance(response, dict):
        merged_payload = {
            **payload,
            "response_id": response.get("id") or payload.get("response_id"),
            "model": response.get("model") or payload.get("model"),
            "status": response.get("status") or payload.get("status"),
        }
        return _build_text_stream_chunk(
            merged_payload,
            content="",
            event_type="response.completed",
            finish_reason="stop",
        )

    return _parse_completed_event(payload)


def _parse_created_event_with_response(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse ``response.created`` events that may embed a response object."""
    response = payload.get("response")
    if isinstance(response, dict):
        merged_payload = {
            **payload,
            "response_id": response.get("id") or payload.get("response_id"),
            "model": response.get("model") or payload.get("model"),
            "status": response.get("status") or payload.get("status"),
        }
        return _build_text_stream_chunk(
            merged_payload,
            content="",
            event_type="response.created",
            finish_reason=None,
        )

    return _parse_created_event(payload)


def _parse_in_progress_event_with_response(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse ``response.in_progress`` events that may embed response object."""
    response = payload.get("response")
    if isinstance(response, dict):
        merged_payload = {
            **payload,
            "response_id": response.get("id") or payload.get("response_id"),
            "model": response.get("model") or payload.get("model"),
            "status": response.get("status") or payload.get("status"),
        }
        return _build_text_stream_chunk(
            merged_payload,
            content="",
            event_type="response.in_progress",
            finish_reason=None,
        )

    return _parse_in_progress_event(payload)


def _parse_response_lifecycle_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse response lifecycle events as lightweight status chunks."""
    event_type = payload.get("type")
    if event_type == "response.created":
        return _parse_created_event_with_response(payload)
    if event_type == "response.in_progress":
        return _parse_in_progress_event_with_response(payload)
    if event_type == "response.completed":
        return _parse_completed_event_with_response(payload)
    if event_type == "response.failed":
        return _parse_failed_event(payload)
    if event_type == "response.cancelled":
        return _parse_cancelled_event(payload)
    if event_type == "response.incomplete":
        return _parse_incomplete_event(payload)
    if event_type == "response.queued":
        return _parse_queued_event(payload)

    return None


def _parse_output_text_annotation_event(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse ``response.output_text.annotation.added`` events."""
    return _build_text_stream_chunk(
        payload,
        content="",
        event_type="response.output_text.annotation.added",
        finish_reason=None,
    )


def _parse_output_item_added_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse ``response.output_item.added`` events."""
    return _parse_output_item_event(payload)


def _parse_output_item_done_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse ``response.output_item.done`` events."""
    return _parse_output_item_event(payload)


def _parse_content_part_added_event(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse ``response.content_part.added`` events."""
    return _parse_content_part_event(payload)


def _parse_content_part_done_event(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse ``response.content_part.done`` events."""
    return _parse_content_part_event(payload)


def _parse_refusal_delta_event_alias(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse alias refusal delta events."""
    return _parse_refusal_delta_event(payload)


def _parse_refusal_done_event_alias(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse alias refusal done events."""
    return _parse_refusal_done_event(payload)


def _parse_reasoning_summary_text_delta_event(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse reasoning summary text delta events."""
    return _parse_summary_text_delta_event(payload)


def _parse_reasoning_summary_text_done_event(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse reasoning summary text done events."""
    return _parse_summary_text_done_event(payload)


def _parse_reasoning_text_delta_event_alias(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse alias reasoning text delta events."""
    return _parse_reasoning_text_delta_event(payload)


def _parse_reasoning_text_done_event_alias(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse alias reasoning text done events."""
    return _parse_reasoning_text_done_event(payload)


def _parse_text_delta_event_alias(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse alias text delta events."""
    return _parse_text_delta_event(payload)


def _parse_text_done_event_alias(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse alias text done events."""
    return _parse_text_done_event(payload)


def _parse_function_call_arguments_delta_event(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse ``response.function_call_arguments.delta`` events."""
    return _build_function_stream_chunk(payload)


def _parse_function_call_arguments_done_event(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse ``response.function_call_arguments.done`` events."""
    return _parse_function_arguments_done_event(payload)


def _parse_error_event_alias(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse alias generic error events."""
    return _parse_error_event(payload)


def _parse_audio_delta_event_alias(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse alias audio delta events."""
    return _parse_audio_delta_event(payload)


def _parse_audio_done_event_alias(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse alias audio done events."""
    return _parse_audio_done_event(payload)


def _parse_audio_transcript_delta_event_alias(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse alias audio transcript delta events."""
    return _parse_audio_transcript_delta_event(payload)


def _parse_audio_transcript_done_event_alias(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse alias audio transcript done events."""
    return _parse_audio_transcript_done_event(payload)


def _parse_lifecycle_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse response lifecycle events."""
    return _parse_response_lifecycle_event(payload)


def _parse_tool_event_alias(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse alias tool progress events."""
    return _parse_tool_event(payload)


def _parse_function_call_event_alias(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse alias function call lifecycle events."""
    return _parse_function_call_event(payload)


def _parse_annotation_event_alias(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse alias annotation events."""
    return _parse_annotation_event(payload)


def _parse_output_item_lifecycle_event_alias(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse alias output item lifecycle events."""
    return _parse_output_item_lifecycle_event(payload)


def _parse_content_part_event_alias(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse alias content part lifecycle events."""
    return _parse_content_part_event(payload)


def _parse_refusal_delta_event_prefixed(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse prefixed refusal delta events."""
    return _parse_refusal_delta_event(payload)


def _parse_refusal_done_event_prefixed(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse prefixed refusal done events."""
    return _parse_refusal_done_event(payload)


def _parse_reasoning_summary_text_delta_event_prefixed(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse prefixed reasoning summary delta events."""
    return _parse_summary_text_delta_event(payload)


def _parse_reasoning_summary_text_done_event_prefixed(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse prefixed reasoning summary done events."""
    return _parse_summary_text_done_event(payload)


def _parse_reasoning_text_delta_event_prefixed(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse prefixed reasoning text delta events."""
    return _parse_reasoning_text_delta_event(payload)


def _parse_reasoning_text_done_event_prefixed(
    payload: dict[str, Any],
) -> LLMStreamChunk | None:
    """Parse prefixed reasoning text done events."""
    return _parse_reasoning_text_done_event(payload)


def _parse_output_text_delta_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse ``response.output_text.delta`` events to neutral chunks."""
    delta = payload.get("delta")
    if not isinstance(delta, str):
        return None
    return _build_text_stream_chunk(
        payload,
        content=delta,
        event_type="response.output_text.delta",
    )


def _parse_output_text_done_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
    """Parse ``response.output_text.done`` events to neutral chunks."""
    text = payload.get("text")
    if not isinstance(text, str):
        return None
    return _build_text_stream_chunk(
        payload,
        content=text,
        event_type="response.output_text.done",
    )


def _parse_completed_event(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse ``response.completed`` events to a terminal neutral chunk."""
    return _build_text_stream_chunk(
        payload,
        content="",
        event_type="response.completed",
        finish_reason="stop",
    )


def _parse_errored_event(payload: dict[str, Any]) -> LLMStreamChunk:
    """Parse failed/cancelled/incomplete events to terminal error chunks."""
    event_type = str(payload.get("type", "response.failed"))
    return _build_text_stream_chunk(
        payload,
        content="",
        event_type=event_type,
        finish_reason="error",
    )


_OPENAI_STREAM_EVENT_PARSERS: dict[
    str,
    Callable[[dict[str, Any]], LLMStreamChunk | None],
] = {
    "response.created": _parse_created_event_with_response,
    "response.in_progress": _parse_in_progress_event_with_response,
    "response.queued": _parse_queued_event,
    "response.output_text.delta": _parse_output_text_delta_event,
    "response.output_text.done": _parse_output_text_done_event,
    "response.text.delta": _parse_text_delta_event_alias,
    "response.text.done": _parse_text_done_event_alias,
    "response.refusal.delta": _parse_refusal_delta_event_prefixed,
    "response.refusal.done": _parse_refusal_done_event_prefixed,
    "response.reasoning_text.delta": _parse_reasoning_text_delta_event_prefixed,
    "response.reasoning_text.done": _parse_reasoning_text_done_event_prefixed,
    "response.reasoning_summary_text.delta": (
        _parse_reasoning_summary_text_delta_event_prefixed
    ),
    "response.reasoning_summary_text.done": (
        _parse_reasoning_summary_text_done_event_prefixed
    ),
    "response.output_text.annotation.added": _parse_annotation_event_alias,
    "response.output_item.added": _parse_output_item_added_event,
    "response.output_item.done": _parse_output_item_done_event,
    "response.content_part.added": _parse_content_part_added_event,
    "response.content_part.done": _parse_content_part_done_event,
    "response.function_call_arguments.delta": (
        _parse_function_call_arguments_delta_event
    ),
    "response.function_call_arguments.done": _parse_function_call_arguments_done_event,
    "response.function_call.in_progress": _parse_function_call_event_alias,
    "response.function_call.completed": _parse_function_call_event_alias,
    "response.file_search_call.in_progress": _parse_tool_event_alias,
    "response.file_search_call.searching": _parse_tool_event_alias,
    "response.file_search_call.completed": _parse_tool_event_alias,
    "response.web_search_call.in_progress": _parse_tool_event_alias,
    "response.web_search_call.searching": _parse_tool_event_alias,
    "response.web_search_call.completed": _parse_tool_event_alias,
    "response.code_interpreter_call.in_progress": _parse_tool_event_alias,
    "response.code_interpreter_call.interpreting": _parse_tool_event_alias,
    "response.code_interpreter_call.completed": _parse_tool_event_alias,
    "response.completed": _parse_completed_event_with_response,
    "response.failed": _parse_failed_event,
    "response.cancelled": _parse_cancelled_event,
    "response.incomplete": _parse_incomplete_event,
    "response.audio.delta": _parse_audio_delta_event_alias,
    "response.audio.done": _parse_audio_done_event_alias,
    "response.audio.transcript.delta": _parse_audio_transcript_delta_event_alias,
    "response.audio.transcript.done": _parse_audio_transcript_done_event_alias,
    "error": _parse_error_event_alias,
}


class OpenAIResponsesStreamAdapter(DefaultLLMStreamAdapter):
    """Map OpenAI Responses stream events to neutral stream chunks."""

    def parse_event_payload(self, payload_line: str) -> LLMStreamChunk | None:
        """Parse one OpenAI Responses event payload into neutral chunk shape."""
        stripped = payload_line.strip()
        if not stripped or stripped == "[DONE]":
            return None

        try:
            payload = json.loads(stripped)
        except JSONDecodeError as exc:
            raise ValueError("Failed to parse LLM stream event payload") from exc

        if not isinstance(payload, dict):
            raise ValueError("Expected JSON object payload for stream event")

        if "choices" in payload:
            return LLMStreamChunk.from_payload(payload)

        event_type = payload.get("type")
        if not isinstance(event_type, str):
            return None

        parser = _OPENAI_STREAM_EVENT_PARSERS.get(event_type)
        if parser is None:
            return None

        return parser(payload)


def build_openai_responses_adapter_set() -> LLMAdapterSet:
    """Return adapter set for OpenAI Responses API integrations."""
    return LLMAdapterSet(
        request_adapter=OpenAIResponsesRequestAdapter(),
        completion_adapter=OpenAIResponsesCompletionAdapter(),
        stream_adapter=OpenAIResponsesStreamAdapter(),
    )
