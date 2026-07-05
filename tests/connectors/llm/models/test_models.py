"""Tests for provider-agnostic LLM contract models."""

from __future__ import annotations

from plynth.connectors.llm.models import (
    LLMCompletion,
    LLMExecutionOptions,
    LLMGenerateRequest,
    LLMMessage,
    LLMStreamChunk,
    LLMToolDefinition,
)


class TestLLMGenerateRequest:
    """Conformance tests for neutral generation request payloads."""

    def test_to_payload_serializes_messages_tools_and_options(self) -> None:
        """Serialize request using only neutral contract fields."""
        request = LLMGenerateRequest(
            messages=[
                LLMMessage(role="system", content="You are concise"),
                {"role": "user", "content": "Hello"},
            ],
            model="demo-model",
            tools=[
                LLMToolDefinition(
                    name="lookup_customer",
                    description="Find customer by id",
                    input_schema={
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                    },
                )
            ],
            options=LLMExecutionOptions(
                temperature=0.2,
                max_tokens=128,
                stream=False,
            ),
            provider_extensions={"provider": {"region": "eu-west-1"}},
        )

        assert request.to_payload() == {
            "messages": [
                {"role": "system", "content": "You are concise"},
                {"role": "user", "content": "Hello"},
            ],
            "model": "demo-model",
            "tools": [
                {
                    "name": "lookup_customer",
                    "description": "Find customer by id",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                    },
                }
            ],
            "options": {"temperature": 0.2, "max_tokens": 128, "stream": False},
            "provider_extensions": {"provider": {"region": "eu-west-1"}},
        }

    def test_with_stream_sets_options_stream_flag(self) -> None:
        """with_stream returns a copy with stream enabled."""
        request = LLMGenerateRequest(messages=[{"role": "user", "content": "Hi"}])

        stream_request = request.with_stream(True)

        assert request.options is None
        assert stream_request.options is not None
        assert stream_request.options.stream is True

    def test_with_stream_updates_existing_options(self) -> None:
        """with_stream toggles stream on an existing options object."""
        request = LLMGenerateRequest(
            messages=[{"role": "user", "content": "Hi"}],
            options=LLMExecutionOptions(stream=False),
        )

        stream_request = request.with_stream(True)

        assert request.options is not None
        assert request.options.stream is False
        assert stream_request.options is not None
        assert stream_request.options.stream is True


class TestLLMCompletionNormalization:
    """Tests for provider payload normalization into generic completion types."""

    def test_from_payload_maps_common_usage_fields(self) -> None:
        """Normalize prompt/completion token names into neutral usage fields."""
        payload = {
            "id": "chatcmpl-1",
            "model": "demo-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        }

        result = LLMCompletion.from_payload(payload)

        assert result.id == "chatcmpl-1"
        assert result.choices[0].message.role == "assistant"
        assert result.usage is not None
        assert result.usage.input_tokens == 11
        assert result.usage.output_tokens == 7
        assert result.usage.total_tokens == 18

    def test_from_payload_uses_fallback_message_when_missing_message_object(
        self,
    ) -> None:
        """Fallback assistant message is used when provider omits message dict."""
        payload = {
            "choices": [{"index": 0, "message": "not-a-dict"}],
            "usage": {},
        }

        result = LLMCompletion.from_payload(payload)

        assert result.choices[0].message.role == "assistant"
        assert result.choices[0].message.content == ""
        assert result.usage is None


class TestLLMStreamChunkNormalization:
    """Tests for provider payload normalization into generic stream chunks."""

    def test_from_payload_maps_delta_content(self) -> None:
        """Normalize stream delta payload into typed chunk model."""
        payload = {
            "id": "chunk-1",
            "model": "demo-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "Hel"},
                    "finish_reason": None,
                }
            ],
        }

        result = LLMStreamChunk.from_payload(payload)

        assert result.id == "chunk-1"
        assert result.choices[0].delta.content == "Hel"

    def test_from_payload_uses_fallback_delta_when_missing_delta_object(self) -> None:
        """Fallback assistant delta is used when provider omits delta dict."""
        payload = {
            "choices": [{"index": 0, "delta": "not-a-dict"}],
        }

        result = LLMStreamChunk.from_payload(payload)

        assert result.choices[0].delta.role == "assistant"
        assert result.choices[0].delta.content == ""
