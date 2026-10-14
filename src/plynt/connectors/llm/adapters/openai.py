"""OpenAI Responses adapters for neutral LLM request, completion, and stream models."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from plynt.connectors.llm.adapters.base import (
    DefaultLLMCompletionAdapter,
    LLMAdapterSet,
    LLMRequestAdapter,
    RoutedEventStreamAdapter,
)
from plynt.connectors.llm.models import (
    LLMGenerateRequest,
    LLMMessage,
    LLMStreamChunk,
    LLMToolDefinition,
)


class _OpenAIRequestMapper:
    """Static mapping helpers for OpenAI Responses request payloads."""

    @staticmethod
    def normalize_role(role: Any) -> str:
        """Return a stable role value for OpenAI payload messages."""
        if isinstance(role, str):
            normalized = role.strip()
            if normalized:
                return normalized
        return "user"

    @staticmethod
    def normalize_content(content: Any) -> str | list[dict[str, Any]]:
        """Return message content in one of the neutral content shapes."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            blocks = [item for item in content if isinstance(item, dict)]
            if blocks:
                return blocks
            return ""
        return str(content)

    @staticmethod
    def message_to_input_item(message: LLMMessage | dict[str, Any]) -> dict[str, Any]:
        """Convert one neutral message to a Responses API input item."""
        if isinstance(message, dict):
            role = _OpenAIRequestMapper.normalize_role(message.get("role"))
            content = _OpenAIRequestMapper.normalize_content(message.get("content"))
            return {"role": role, "content": content}

        return {
            "role": _OpenAIRequestMapper.normalize_role(message.role),
            "content": _OpenAIRequestMapper.normalize_content(message.content),
        }

    @staticmethod
    def tool_to_openai_function(tool: LLMToolDefinition) -> dict[str, Any]:
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

    @staticmethod
    def apply_request_options(
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
    """Serialize neutral requests to OpenAI Responses API payloads."""

    def to_provider_payload(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Build OpenAI Responses request payload.

        Args:
            request: Neutral generation request.
            stream: Whether to request streaming mode.

        Returns:
            Provider payload compatible with the Responses API.

        """
        payload: dict[str, Any] = {
            "input": [
                _OpenAIRequestMapper.message_to_input_item(message)
                for message in request.messages
            ],
            "stream": stream,
        }

        if request.model is not None:
            payload["model"] = request.model

        if request.tools:
            payload["tools"] = [
                _OpenAIRequestMapper.tool_to_openai_function(tool)
                for tool in request.tools
            ]

        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice

        _OpenAIRequestMapper.apply_request_options(payload, request)

        if request.provider_extensions is not None:
            payload.update(request.provider_extensions)

        return payload


class _OpenAICompletionMapper:
    """Static mapping helpers for OpenAI completion payloads."""

    @staticmethod
    def extract_output_text(output_items: list[dict[str, Any]]) -> str:
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
                if part.get("type") != "output_text":
                    continue

                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)

        return "".join(chunks)

    @staticmethod
    def extract_function_tool_calls(
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
    """Normalize OpenAI completion payloads to the neutral contract."""

    def to_neutral_completion_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize OpenAI provider payload keys and structure.

        Args:
            payload: Raw completion payload from OpenAI.

        Returns:
            Neutral completion payload with choices and usage.

        """
        raw_output = payload.get("output")
        output_items: list[dict[str, Any]] = (
            [item for item in raw_output if isinstance(item, dict)]
            if isinstance(raw_output, list)
            else []
        )

        message: dict[str, Any] = {
            "role": "assistant",
            "content": _OpenAICompletionMapper.extract_output_text(output_items),
        }

        tool_calls = _OpenAICompletionMapper.extract_function_tool_calls(output_items)
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
                    "event_kind": "completion",
                    "response_status": payload.get("status"),
                }
            },
        }


class _OpenAIStreamChunkFactory:
    """Static builders for neutral stream chunks from OpenAI events."""

    _EVENT_KIND_BY_PREFIX: ClassVar[tuple[tuple[str, str], ...]] = (
        ("response.function_call", "tool"),
        ("response.audio", "audio"),
        ("response.reasoning", "reasoning"),
        ("response.refusal", "refusal"),
        ("response.output_text", "text"),
        ("response.text", "text"),
        ("response.output_item", "output_item"),
        ("response.content_part", "content_part"),
        ("response.file_search_call", "tool_progress"),
        ("response.web_search_call", "tool_progress"),
        ("response.code_interpreter_call", "tool_progress"),
    )

    _LIFECYCLE_EVENT_TYPES: ClassVar[set[str]] = {
        "response.created",
        "response.in_progress",
        "response.queued",
        "response.completed",
        "response.failed",
        "response.cancelled",
        "response.incomplete",
    }

    @staticmethod
    def classify_event_kind(event_type: str) -> str:
        """Classify one OpenAI event type to a neutral stream event kind."""
        if event_type == "error":
            return "error"
        if event_type in _OpenAIStreamChunkFactory._LIFECYCLE_EVENT_TYPES:
            return "lifecycle"
        if event_type == "response.output_text.annotation.added":
            return "annotation"

        for prefix, kind in _OpenAIStreamChunkFactory._EVENT_KIND_BY_PREFIX:
            if event_type.startswith(prefix):
                return kind

        return "unknown"

    @staticmethod
    def build_text_chunk(
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
                        "event_kind": _OpenAIStreamChunkFactory.classify_event_kind(
                            event_type
                        ),
                        "status": payload.get("status"),
                    }
                },
            }
        )

    @staticmethod
    def function_chunk_payload(
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
                    "event_kind": _OpenAIStreamChunkFactory.classify_event_kind(
                        event_type
                    ),
                }
            },
        }

    @staticmethod
    def build_function_chunk_from_parts(
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
            _OpenAIStreamChunkFactory.function_chunk_payload(
                payload,
                name=normalized_name,
                arguments=arguments,
                call_id=normalized_call_id,
                event_type=event_type,
            )
        )

    @staticmethod
    def build_function_chunk(payload: dict[str, Any]) -> LLMStreamChunk | None:
        """Build one neutral tool-call delta chunk from arguments-delta event."""
        return _OpenAIStreamChunkFactory.build_function_chunk_from_parts(
            payload,
            name=payload.get("name"),
            arguments=payload.get("delta"),
            call_id=payload.get("call_id") or payload.get("item_id"),
            event_type="response.function_call_arguments.delta",
        )


class _OpenAIStreamEventParser:
    """Static parsers for OpenAI stream events into neutral chunks."""

    @staticmethod
    def merge_response_payload(payload: dict[str, Any]) -> dict[str, Any]:
        """Merge top-level payload with nested response metadata when present."""
        response = payload.get("response")
        if not isinstance(response, dict):
            return payload

        return {
            **payload,
            "response_id": response.get("id") or payload.get("response_id"),
            "model": response.get("model") or payload.get("model"),
            "status": response.get("status") or payload.get("status"),
        }

    @staticmethod
    def parse_output_item_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
        """Parse output-item lifecycle events."""
        item = payload.get("item")
        if not isinstance(item, dict):
            return None

        event_type = str(payload.get("type", "response.output_item.added"))
        item_type = item.get("type")

        if item_type == "function_call":
            return _OpenAIStreamChunkFactory.build_function_chunk_from_parts(
                payload,
                name=item.get("name"),
                arguments=item.get("arguments"),
                call_id=item.get("call_id") or item.get("id"),
                event_type=event_type,
            )

        if item_type == "message":
            text = _OpenAICompletionMapper.extract_output_text([item])
            return _OpenAIStreamChunkFactory.build_text_chunk(
                payload,
                content=text,
                event_type=event_type,
            )

        return None

    @staticmethod
    def parse_text_delta_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
        """Parse text-delta event variants."""
        delta = payload.get("delta")
        if not isinstance(delta, str):
            return None

        event_type = str(payload.get("type", "response.output_text.delta"))
        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content=delta,
            event_type=event_type,
        )

    @staticmethod
    def parse_text_done_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
        """Parse text-done event variants."""
        text = payload.get("text")
        if not isinstance(text, str):
            return None

        event_type = str(payload.get("type", "response.output_text.done"))
        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content=text,
            event_type=event_type,
        )

    @staticmethod
    def parse_refusal_delta_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
        """Parse refusal-delta events as assistant content chunks."""
        delta = payload.get("delta")
        if not isinstance(delta, str):
            return None

        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content=delta,
            event_type="response.refusal.delta",
        )

    @staticmethod
    def parse_refusal_done_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
        """Parse refusal-done events as assistant content chunks."""
        refusal = payload.get("refusal")
        if not isinstance(refusal, str):
            return None

        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content=refusal,
            event_type="response.refusal.done",
        )

    @staticmethod
    def parse_reasoning_text_delta_event(
        payload: dict[str, Any],
    ) -> LLMStreamChunk | None:
        """Parse reasoning-text-delta events."""
        delta = payload.get("delta")
        if not isinstance(delta, str):
            return None

        event_type = str(payload.get("type", "response.reasoning_text.delta"))
        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content=delta,
            event_type=event_type,
        )

    @staticmethod
    def parse_reasoning_text_done_event(
        payload: dict[str, Any],
    ) -> LLMStreamChunk | None:
        """Parse reasoning-text-done events."""
        text = payload.get("text")
        if not isinstance(text, str):
            return None

        event_type = str(payload.get("type", "response.reasoning_text.done"))
        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content=text,
            event_type=event_type,
        )

    @staticmethod
    def parse_reasoning_summary_text_delta_event(
        payload: dict[str, Any],
    ) -> LLMStreamChunk | None:
        """Parse reasoning-summary-delta events."""
        delta = payload.get("delta")
        if not isinstance(delta, str):
            return None

        event_type = str(payload.get("type", "response.reasoning_summary_text.delta"))
        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content=delta,
            event_type=event_type,
        )

    @staticmethod
    def parse_reasoning_summary_text_done_event(
        payload: dict[str, Any],
    ) -> LLMStreamChunk | None:
        """Parse reasoning-summary-done events."""
        text = payload.get("text")
        if not isinstance(text, str):
            return None

        event_type = str(payload.get("type", "response.reasoning_summary_text.done"))
        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content=text,
            event_type=event_type,
        )

    @staticmethod
    def parse_function_call_arguments_delta_event(
        payload: dict[str, Any],
    ) -> LLMStreamChunk | None:
        """Parse function-call-arguments-delta events."""
        return _OpenAIStreamChunkFactory.build_function_chunk(payload)

    @staticmethod
    def parse_function_call_arguments_done_event(
        payload: dict[str, Any],
    ) -> LLMStreamChunk | None:
        """Parse function-call-arguments-done events."""
        item = payload.get("item")
        if isinstance(item, dict):
            if item.get("type") != "function_call":
                return None
            return _OpenAIStreamChunkFactory.build_function_chunk_from_parts(
                payload,
                name=item.get("name"),
                arguments=item.get("arguments"),
                call_id=item.get("call_id") or item.get("id"),
                event_type="response.function_call_arguments.done",
            )

        return _OpenAIStreamChunkFactory.build_function_chunk_from_parts(
            payload,
            name=payload.get("name"),
            arguments=payload.get("arguments"),
            call_id=payload.get("call_id") or payload.get("item_id"),
            event_type="response.function_call_arguments.done",
        )

    @staticmethod
    def parse_function_call_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
        """Parse function-call lifecycle events carrying full item payload."""
        item = payload.get("item")
        if not isinstance(item, dict):
            return None
        if item.get("type") != "function_call":
            return None

        return _OpenAIStreamChunkFactory.build_function_chunk_from_parts(
            payload,
            name=item.get("name"),
            arguments=item.get("arguments"),
            call_id=item.get("call_id") or item.get("id"),
            event_type=str(payload.get("type", "response.function_call.completed")),
        )

    @staticmethod
    def parse_annotation_event(payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse output-text-annotation events."""
        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content="",
            event_type="response.output_text.annotation.added",
        )

    @staticmethod
    def parse_content_part_event(payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse content-part lifecycle events into empty status chunks."""
        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content="",
            event_type=str(payload.get("type", "response.content_part.added")),
        )

    @staticmethod
    def parse_tool_event(payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse tool progress events into empty status chunks."""
        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content="",
            event_type=str(payload.get("type", "response.tool.in_progress")),
        )

    @staticmethod
    def parse_audio_delta_event(payload: dict[str, Any]) -> LLMStreamChunk | None:
        """Parse audio-delta events."""
        delta = payload.get("delta")
        if not isinstance(delta, str):
            return None

        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content=delta,
            event_type="response.audio.delta",
        )

    @staticmethod
    def parse_audio_done_event(payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse audio-done events as lightweight completion markers."""
        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content="",
            event_type="response.audio.done",
        )

    @staticmethod
    def parse_audio_transcript_delta_event(
        payload: dict[str, Any],
    ) -> LLMStreamChunk | None:
        """Parse audio-transcript-delta events."""
        delta = payload.get("delta")
        if not isinstance(delta, str):
            return None

        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content=delta,
            event_type="response.audio.transcript.delta",
        )

    @staticmethod
    def parse_audio_transcript_done_event(
        payload: dict[str, Any],
    ) -> LLMStreamChunk | None:
        """Parse audio-transcript-done events."""
        transcript = payload.get("transcript")
        if not isinstance(transcript, str):
            return None

        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content=transcript,
            event_type="response.audio.transcript.done",
        )

    @staticmethod
    def _parse_lifecycle_event_with_response(
        payload: dict[str, Any],
        *,
        event_type: str,
        finish_reason: str | None,
    ) -> LLMStreamChunk:
        """Parse one lifecycle event that may include a nested response object."""
        merged_payload = _OpenAIStreamEventParser.merge_response_payload(payload)
        return _OpenAIStreamChunkFactory.build_text_chunk(
            merged_payload,
            content="",
            event_type=event_type,
            finish_reason=finish_reason,
        )

    @staticmethod
    def parse_created_event(payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse response-created events."""
        return _OpenAIStreamEventParser._parse_lifecycle_event_with_response(
            payload,
            event_type="response.created",
            finish_reason=None,
        )

    @staticmethod
    def parse_in_progress_event(payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse response-in-progress events."""
        return _OpenAIStreamEventParser._parse_lifecycle_event_with_response(
            payload,
            event_type="response.in_progress",
            finish_reason=None,
        )

    @staticmethod
    def parse_queued_event(payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse response-queued events."""
        return _OpenAIStreamEventParser._parse_lifecycle_event_with_response(
            payload,
            event_type="response.queued",
            finish_reason=None,
        )

    @staticmethod
    def parse_completed_event(payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse response-completed events."""
        return _OpenAIStreamEventParser._parse_lifecycle_event_with_response(
            payload,
            event_type="response.completed",
            finish_reason="stop",
        )

    @staticmethod
    def parse_failed_event(payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse response-failed events."""
        return _OpenAIStreamEventParser._parse_lifecycle_event_with_response(
            payload,
            event_type="response.failed",
            finish_reason="error",
        )

    @staticmethod
    def parse_cancelled_event(payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse response-cancelled events."""
        return _OpenAIStreamEventParser._parse_lifecycle_event_with_response(
            payload,
            event_type="response.cancelled",
            finish_reason="error",
        )

    @staticmethod
    def parse_incomplete_event(payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse response-incomplete events."""
        return _OpenAIStreamEventParser._parse_lifecycle_event_with_response(
            payload,
            event_type="response.incomplete",
            finish_reason="error",
        )

    @staticmethod
    def parse_error_event(payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse generic error events to terminal error chunks."""
        return _OpenAIStreamChunkFactory.build_text_chunk(
            payload,
            content="",
            event_type="error",
            finish_reason="error",
        )


class _OpenAIStreamEventRouter:
    """Router for OpenAI stream event parsers by event type."""

    _EVENT_PARSERS: ClassVar[
        dict[str, Callable[[dict[str, Any]], LLMStreamChunk | None]]
    ] = {
        "response.created": _OpenAIStreamEventParser.parse_created_event,
        "response.in_progress": _OpenAIStreamEventParser.parse_in_progress_event,
        "response.queued": _OpenAIStreamEventParser.parse_queued_event,
        "response.completed": _OpenAIStreamEventParser.parse_completed_event,
        "response.failed": _OpenAIStreamEventParser.parse_failed_event,
        "response.cancelled": _OpenAIStreamEventParser.parse_cancelled_event,
        "response.incomplete": _OpenAIStreamEventParser.parse_incomplete_event,
        "response.output_text.delta": _OpenAIStreamEventParser.parse_text_delta_event,
        "response.output_text.done": _OpenAIStreamEventParser.parse_text_done_event,
        "response.text.delta": _OpenAIStreamEventParser.parse_text_delta_event,
        "response.text.done": _OpenAIStreamEventParser.parse_text_done_event,
        "response.refusal.delta": _OpenAIStreamEventParser.parse_refusal_delta_event,
        "response.refusal.done": _OpenAIStreamEventParser.parse_refusal_done_event,
        "response.reasoning_text.delta": (
            _OpenAIStreamEventParser.parse_reasoning_text_delta_event
        ),
        "response.reasoning_text.done": (
            _OpenAIStreamEventParser.parse_reasoning_text_done_event
        ),
        "response.reasoning_summary_text.delta": (
            _OpenAIStreamEventParser.parse_reasoning_summary_text_delta_event
        ),
        "response.reasoning_summary_text.done": (
            _OpenAIStreamEventParser.parse_reasoning_summary_text_done_event
        ),
        "response.output_text.annotation.added": (
            _OpenAIStreamEventParser.parse_annotation_event
        ),
        "response.output_item.added": _OpenAIStreamEventParser.parse_output_item_event,
        "response.output_item.done": _OpenAIStreamEventParser.parse_output_item_event,
        "response.content_part.added": (
            _OpenAIStreamEventParser.parse_content_part_event
        ),
        "response.content_part.done": _OpenAIStreamEventParser.parse_content_part_event,
        "response.function_call_arguments.delta": (
            _OpenAIStreamEventParser.parse_function_call_arguments_delta_event
        ),
        "response.function_call_arguments.done": (
            _OpenAIStreamEventParser.parse_function_call_arguments_done_event
        ),
        "response.function_call.in_progress": (
            _OpenAIStreamEventParser.parse_function_call_event
        ),
        "response.function_call.completed": (
            _OpenAIStreamEventParser.parse_function_call_event
        ),
        "response.file_search_call.in_progress": (
            _OpenAIStreamEventParser.parse_tool_event
        ),
        "response.file_search_call.searching": (
            _OpenAIStreamEventParser.parse_tool_event
        ),
        "response.file_search_call.completed": (
            _OpenAIStreamEventParser.parse_tool_event
        ),
        "response.web_search_call.in_progress": (
            _OpenAIStreamEventParser.parse_tool_event
        ),
        "response.web_search_call.searching": (
            _OpenAIStreamEventParser.parse_tool_event
        ),
        "response.web_search_call.completed": (
            _OpenAIStreamEventParser.parse_tool_event
        ),
        "response.code_interpreter_call.in_progress": (
            _OpenAIStreamEventParser.parse_tool_event
        ),
        "response.code_interpreter_call.interpreting": (
            _OpenAIStreamEventParser.parse_tool_event
        ),
        "response.code_interpreter_call.completed": (
            _OpenAIStreamEventParser.parse_tool_event
        ),
        "response.audio.delta": _OpenAIStreamEventParser.parse_audio_delta_event,
        "response.audio.done": _OpenAIStreamEventParser.parse_audio_done_event,
        "response.audio.transcript.delta": (
            _OpenAIStreamEventParser.parse_audio_transcript_delta_event
        ),
        "response.audio.transcript.done": (
            _OpenAIStreamEventParser.parse_audio_transcript_done_event
        ),
        "error": _OpenAIStreamEventParser.parse_error_event,
    }

    @staticmethod
    def parser_for(
        event_type: str,
    ) -> Callable[[dict[str, Any]], LLMStreamChunk | None] | None:
        """Return parser callable for one event type, if supported."""
        return _OpenAIStreamEventRouter._EVENT_PARSERS.get(event_type)

    @staticmethod
    def event_parsers() -> dict[str, Callable[[dict[str, Any]], LLMStreamChunk | None]]:
        """Return full event parser mapping for OpenAI stream events."""
        return _OpenAIStreamEventRouter._EVENT_PARSERS


class OpenAIResponsesStreamAdapter(RoutedEventStreamAdapter):
    """Normalize OpenAI stream events to neutral stream chunks."""

    def get_event_parsers(
        self,
    ) -> dict[str, Callable[[dict[str, Any]], LLMStreamChunk | None]]:
        """Return event parser mapping used for OpenAI stream routing."""
        return _OpenAIStreamEventRouter.event_parsers()


def build_openai_responses_adapter_set() -> LLMAdapterSet:
    """Build adapter set for OpenAI Responses API integrations."""
    return LLMAdapterSet(
        request_adapter=OpenAIResponsesRequestAdapter(),
        completion_adapter=OpenAIResponsesCompletionAdapter(),
        stream_adapter=OpenAIResponsesStreamAdapter(),
    )
