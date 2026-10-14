"""Anthropic adapter implementations for ``plynt.connectors.llm``."""

from __future__ import annotations

import contextvars
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

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


class _AnthropicRequestMapper:
    """Static mapping helpers for Anthropic request payloads."""

    @staticmethod
    def normalize_role(role: str | None) -> str:
        """Return an Anthropic-compatible role."""
        if role == "assistant":
            return "assistant"
        return "user"

    @staticmethod
    def message_content_as_text(content: Any) -> str:
        """Render arbitrary neutral message content to text."""
        if isinstance(content, str):
            return content
        if content is None:
            return ""
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            if parts:
                return "".join(parts)
        return json.dumps(content)

    @staticmethod
    def message_content_to_blocks(content: Any) -> list[dict[str, Any]]:
        """Map neutral message content to Anthropic message blocks."""
        if isinstance(content, str):
            return [{"type": "text", "text": content}]

        if content is None:
            return [{"type": "text", "text": ""}]

        if isinstance(content, list):
            blocks = [item for item in content if isinstance(item, dict)]
            if blocks:
                return blocks
            return [{"type": "text", "text": ""}]

        return [{"type": "text", "text": str(content)}]

    @staticmethod
    def to_anthropic_message(message: LLMMessage | dict[str, Any]) -> dict[str, Any]:
        """Map one neutral message to Anthropic Messages payload shape."""
        if isinstance(message, dict):
            role = str(message.get("role", "user"))
            content = message.get("content")
            tool_call_id = message.get("tool_call_id")
        else:
            role = message.role
            content = message.content
            tool_call_id = message.tool_call_id

        if isinstance(tool_call_id, str) and tool_call_id:
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call_id,
                        "content": _AnthropicRequestMapper.message_content_as_text(
                            content
                        ),
                    }
                ],
            }

        return {
            "role": _AnthropicRequestMapper.normalize_role(role),
            "content": _AnthropicRequestMapper.message_content_to_blocks(content),
        }

    @staticmethod
    def extract_system_text(message: LLMMessage | dict[str, Any]) -> str | None:
        """Extract one system-message text fragment when present."""
        if isinstance(message, dict):
            role = str(message.get("role", "user"))
            content = message.get("content")
        else:
            role = message.role
            content = message.content

        if role != "system":
            return None

        text = _AnthropicRequestMapper.message_content_as_text(content)
        if text:
            return text
        return None

    @staticmethod
    def tool_to_anthropic_tool(tool: LLMToolDefinition) -> dict[str, Any]:
        """Map one neutral tool definition to Anthropic tool shape."""
        payload: dict[str, Any] = {
            "name": tool.name,
            "input_schema": tool.input_schema or {"type": "object", "properties": {}},
        }
        if tool.description is not None:
            payload["description"] = tool.description
        return payload

    @staticmethod
    def apply_request_options(
        payload: dict[str, Any],
        request: LLMGenerateRequest,
    ) -> None:
        """Apply neutral execution options onto an Anthropic payload."""
        if request.options is None:
            if "max_tokens" not in payload:
                payload["max_tokens"] = 1024
            return

        if request.options.temperature is not None:
            payload["temperature"] = request.options.temperature
        if request.options.max_tokens is not None:
            payload["max_tokens"] = request.options.max_tokens
        if request.options.top_p is not None:
            payload["top_p"] = request.options.top_p
        if request.options.metadata is not None:
            payload["metadata"] = request.options.metadata

        if request.options.provider_extensions is not None:
            payload.update(request.options.provider_extensions)

        if "max_tokens" not in payload:
            payload["max_tokens"] = 1024


class _AnthropicCompletionMapper:
    """Static mapping helpers for Anthropic completion payloads."""

    @staticmethod
    def extract_text_content(content: Any) -> str:
        """Extract concatenated text from Anthropic content blocks."""
        if not isinstance(content, list):
            return ""

        chunks: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "text":
                continue
            text = block.get("text")
            if isinstance(text, str):
                chunks.append(text)

        return "".join(chunks)

    @staticmethod
    def extract_tool_calls(content: Any) -> list[dict[str, Any]]:
        """Extract Anthropic ``tool_use`` blocks to neutral ``tool_calls``."""
        if not isinstance(content, list):
            return []

        tool_calls: list[dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue

            name = block.get("name")
            if not isinstance(name, str):
                continue

            input_payload = block.get("input")
            if isinstance(input_payload, str):
                arguments = input_payload
            else:
                arguments = json.dumps(
                    input_payload if input_payload is not None else {}
                )

            tool_calls.append(
                {
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": arguments,
                    },
                }
            )

        return tool_calls

    @staticmethod
    def map_finish_reason(stop_reason: Any) -> str | None:
        """Map Anthropic stop reasons to neutral finish reasons."""
        if not isinstance(stop_reason, str):
            return None
        if stop_reason in {"end_turn", "stop_sequence"}:
            return "stop"
        return stop_reason


class _AnthropicStreamChunkFactory:
    """Static builders for neutral stream chunks from Anthropic events."""

    @staticmethod
    def classify_event_kind(event_type: str) -> str:
        """Classify one Anthropic event type to a neutral stream event kind."""
        if event_type == "error":
            return "error"
        if event_type in {"message_start", "message_stop", "message_delta"}:
            return "lifecycle"
        if event_type == "content_block_start":
            return "tool"
        if event_type == "content_block_delta.text_delta":
            return "text"
        if event_type == "content_block_delta.input_json_delta":
            return "tool"
        return "unknown"

    @staticmethod
    def build_text_chunk(
        *,
        response_id: str | None,
        model: str | None,
        content: str,
        event_type: str,
        finish_reason: str | None = None,
    ) -> LLMStreamChunk:
        """Build one neutral text stream chunk."""
        return LLMStreamChunk.from_payload(
            {
                "id": response_id,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": content,
                        },
                        "finish_reason": finish_reason,
                    }
                ],
                "provider_extensions": {
                    "anthropic": {
                        "event_type": event_type,
                        "event_kind": _AnthropicStreamChunkFactory.classify_event_kind(
                            event_type
                        ),
                    }
                },
            }
        )

    @staticmethod
    def build_function_chunk(
        *,
        response_id: str | None,
        model: str | None,
        call_id: str | None,
        name: str,
        arguments: str,
        event_type: str,
    ) -> LLMStreamChunk:
        """Build one neutral function-call stream chunk."""
        return LLMStreamChunk.from_payload(
            {
                "id": response_id,
                "model": model,
                "choices": [
                    {
                        "index": 0,
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
                    "anthropic": {
                        "event_type": event_type,
                        "event_kind": _AnthropicStreamChunkFactory.classify_event_kind(
                            event_type
                        ),
                    }
                },
            }
        )


@dataclass
class _AnthropicStreamState:
    """Per-stream parsing state for Anthropic stream-event normalization."""

    response_id: str | None = None
    model: str | None = None
    tool_state: dict[int, tuple[str | None, str]] = field(default_factory=dict)


class AnthropicMessagesRequestAdapter(LLMRequestAdapter):
    """Serialize neutral requests to Anthropic Messages API payloads."""

    def to_provider_payload(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Build Anthropic Messages request payload.

        Args:
            request: Neutral generation request.
            stream: Whether to request streaming mode.

        Returns:
            Provider payload compatible with the Messages API.

        """
        payload: dict[str, Any] = {
            "messages": [],
            "stream": stream,
        }

        if request.model is not None:
            payload["model"] = request.model

        system_parts: list[str] = []
        for message in request.messages:
            system_text = _AnthropicRequestMapper.extract_system_text(message)
            if system_text is not None:
                system_parts.append(system_text)
                continue

            payload["messages"].append(
                _AnthropicRequestMapper.to_anthropic_message(message)
            )

        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        if request.tools:
            payload["tools"] = [
                _AnthropicRequestMapper.tool_to_anthropic_tool(tool)
                for tool in request.tools
            ]

        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice

        _AnthropicRequestMapper.apply_request_options(payload, request)

        if request.provider_extensions is not None:
            payload.update(request.provider_extensions)

        return payload


class AnthropicMessagesCompletionAdapter(DefaultLLMCompletionAdapter):
    """Normalize Anthropic completion payloads to the neutral contract."""

    def to_neutral_completion_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize Anthropic provider payload keys and structure.

        Args:
            payload: Raw completion payload from Anthropic.

        Returns:
            Neutral completion payload with choices and usage.

        """
        content = payload.get("content")

        message: dict[str, Any] = {
            "role": "assistant",
            "content": _AnthropicCompletionMapper.extract_text_content(content),
        }

        tool_calls = _AnthropicCompletionMapper.extract_tool_calls(content)
        if tool_calls:
            message["tool_calls"] = tool_calls

        stop_reason = payload.get("stop_reason")

        return {
            "id": payload.get("id"),
            "model": payload.get("model"),
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": _AnthropicCompletionMapper.map_finish_reason(
                        stop_reason
                    ),
                }
            ],
            "usage": payload.get("usage"),
            "provider_extensions": {
                "anthropic": {
                    "event_kind": "completion",
                    "stop_reason": stop_reason,
                    "stop_sequence": payload.get("stop_sequence"),
                }
            },
        }


class AnthropicMessagesStreamAdapter(RoutedEventStreamAdapter):
    """Normalize Anthropic stream events to neutral stream chunks."""

    def __init__(self) -> None:
        """Initialize stream parser routing and isolated parse-state storage."""
        self._state_var: contextvars.ContextVar[_AnthropicStreamState | None] = (
            contextvars.ContextVar(
                f"{self.__class__.__name__}.state",
                default=None,
            )
        )
        self._event_parsers = self._build_event_parsers()

    def _state(self) -> _AnthropicStreamState:
        """Return the current context-local parser state."""
        state = self._state_var.get()
        if state is None:
            state = _AnthropicStreamState()
            self._state_var.set(state)
        return state

    def _build_event_parsers(
        self,
    ) -> dict[str, Callable[[dict[str, Any]], LLMStreamChunk | None]]:
        """Build event parser mapping for Anthropic stream events."""
        return {
            "content_block_delta": self._parse_content_block_delta,
            "content_block_start": self._parse_content_block_start,
            "error": self._parse_error,
            "message_delta": self._parse_message_delta,
            "message_start": self._parse_message_start,
            "message_stop": self._parse_message_stop,
        }

    def get_event_parsers(
        self,
    ) -> dict[str, Callable[[dict[str, Any]], LLMStreamChunk | None]]:
        """Return event parser mapping used for Anthropic stream routing."""
        return self._event_parsers

    def _parse_message_start(self, payload: dict[str, Any]) -> LLMStreamChunk | None:
        """Parse ``message_start`` events."""
        state = self._state()
        message = payload.get("message")
        if isinstance(message, dict):
            state.response_id = message.get("id")
            state.model = message.get("model")
        state.tool_state.clear()
        return None

    def _parse_message_stop(self, payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse ``message_stop`` events."""
        state = self._state()
        state.tool_state.clear()
        return _AnthropicStreamChunkFactory.build_text_chunk(
            response_id=state.response_id,
            model=state.model,
            content="",
            event_type=str(payload.get("type", "message_stop")),
            finish_reason="stop",
        )

    def _parse_error(self, payload: dict[str, Any]) -> LLMStreamChunk:
        """Parse ``error`` events."""
        state = self._state()
        state.tool_state.clear()
        return _AnthropicStreamChunkFactory.build_text_chunk(
            response_id=state.response_id,
            model=state.model,
            content="",
            event_type=str(payload.get("type", "error")),
            finish_reason="error",
        )

    def _parse_content_block_start(
        self,
        payload: dict[str, Any],
    ) -> LLMStreamChunk | None:
        """Parse ``content_block_start`` events."""
        block = payload.get("content_block")
        if not isinstance(block, dict):
            return None

        index = payload.get("index")
        if not isinstance(index, int):
            return None

        if block.get("type") != "tool_use":
            return None

        name = block.get("name")
        if not isinstance(name, str) or not name:
            name = "function"
        call_id = block.get("id") if isinstance(block.get("id"), str) else None
        state = self._state()
        state.tool_state[index] = (call_id, name)

        input_payload = block.get("input")
        arguments = (
            input_payload
            if isinstance(input_payload, str)
            else json.dumps(input_payload if input_payload is not None else {})
        )

        return _AnthropicStreamChunkFactory.build_function_chunk(
            response_id=state.response_id,
            model=state.model,
            call_id=call_id,
            name=name,
            arguments=arguments,
            event_type="content_block_start",
        )

    def _parse_content_block_delta(
        self,
        payload: dict[str, Any],
    ) -> LLMStreamChunk | None:
        """Parse ``content_block_delta`` events."""
        delta = payload.get("delta")
        if not isinstance(delta, dict):
            return None

        delta_type = delta.get("type")
        if delta_type == "text_delta":
            text = delta.get("text")
            if not isinstance(text, str):
                return None
            state = self._state()
            return _AnthropicStreamChunkFactory.build_text_chunk(
                response_id=state.response_id,
                model=state.model,
                content=text,
                event_type="content_block_delta.text_delta",
            )

        if delta_type == "input_json_delta":
            partial_json = delta.get("partial_json")
            if not isinstance(partial_json, str):
                return None

            index = payload.get("index")
            if not isinstance(index, int):
                return None

            state = self._state()
            call_id, name = state.tool_state.get(index, (None, "function"))
            return _AnthropicStreamChunkFactory.build_function_chunk(
                response_id=state.response_id,
                model=state.model,
                call_id=call_id,
                name=name,
                arguments=partial_json,
                event_type="content_block_delta.input_json_delta",
            )

        return None

    def _parse_message_delta(self, payload: dict[str, Any]) -> LLMStreamChunk | None:
        """Parse ``message_delta`` events."""
        delta = payload.get("delta")
        if not isinstance(delta, dict):
            return None

        finish_reason = _AnthropicCompletionMapper.map_finish_reason(
            delta.get("stop_reason")
        )
        if finish_reason is None:
            return None

        state = self._state()
        return _AnthropicStreamChunkFactory.build_text_chunk(
            response_id=state.response_id,
            model=state.model,
            content="",
            event_type="message_delta",
            finish_reason=finish_reason,
        )


def build_anthropic_messages_adapter_set() -> LLMAdapterSet:
    """Build adapter set for Anthropic Messages API integrations."""
    return LLMAdapterSet(
        request_adapter=AnthropicMessagesRequestAdapter(),
        completion_adapter=AnthropicMessagesCompletionAdapter(),
        stream_adapter=AnthropicMessagesStreamAdapter(),
    )
