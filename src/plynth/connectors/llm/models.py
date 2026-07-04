"""Typed, provider-agnostic LLM contract models.

These models define a neutral request and response contract for LLM-style
chat completion workflows. Provider-specific payload details must remain
opaque to this module and can be carried via ``provider_extensions`` fields.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "LLMCompletion",
    "LLMCompletionChoice",
    "LLMExecutionOptions",
    "LLMGenerateRequest",
    "LLMMessage",
    "LLMStreamChoice",
    "LLMStreamChunk",
    "LLMToolCall",
    "LLMToolCallFunction",
    "LLMToolDefinition",
    "LLMUsage",
]


class LLMToolDefinition(BaseModel):
    """Neutral tool descriptor for optional tool-calling workflows."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = Field(
        default=None,
        serialization_alias="inputSchema",
    )


class LLMToolCallFunction(BaseModel):
    """Function call payload emitted by a model."""

    name: str
    arguments: str


class LLMToolCall(BaseModel):
    """Tool-call instruction emitted by a model."""

    id: str | None = None
    type: str = "function"
    function: LLMToolCallFunction


class LLMMessage(BaseModel):
    """Neutral message unit for prompts and completions."""

    model_config = ConfigDict(extra="allow")

    role: str
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    tool_calls: list[LLMToolCall] | None = None
    tool_call_id: str | None = None


class LLMUsage(BaseModel):
    """Normalized token usage metrics."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> LLMUsage | None:
        """Build normalized usage from provider payload fields.

        Supports both neutral names (``input_tokens``) and common provider
        names (``prompt_tokens`` / ``completion_tokens``).
        """
        if payload is None:
            return None

        input_tokens = payload.get("input_tokens")
        if input_tokens is None:
            input_tokens = payload.get("prompt_tokens")

        output_tokens = payload.get("output_tokens")
        if output_tokens is None:
            output_tokens = payload.get("completion_tokens")

        total_tokens = payload.get("total_tokens")

        if input_tokens is None and output_tokens is None and total_tokens is None:
            return None

        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )


class LLMExecutionOptions(BaseModel):
    """Execution options that remain neutral across providers."""

    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stream: bool = False
    metadata: dict[str, str] | None = None
    provider_extensions: dict[str, Any] | None = None


class LLMGenerateRequest(BaseModel):
    """Request contract for chat-style generation."""

    model_config = ConfigDict(populate_by_name=True)

    messages: list[LLMMessage | dict[str, Any]]
    model: str | None = None
    tools: list[LLMToolDefinition] | None = None
    tool_choice: str | dict[str, Any] | None = None
    options: LLMExecutionOptions | None = None
    provider_extensions: dict[str, Any] | None = None

    def with_stream(self, stream: bool = True) -> LLMGenerateRequest:
        """Return a copy with ``options.stream`` set to the given value."""
        clone = self.model_copy(deep=True)
        if clone.options is None:
            clone.options = LLMExecutionOptions(stream=stream)
            return clone

        clone.options.stream = stream
        return clone

    def to_payload(self) -> dict[str, Any]:
        """Serialize the request using neutral wire keys only."""
        payload = self.model_dump(mode="json", by_alias=True, exclude_none=True)
        payload["messages"] = [
            msg.model_dump(mode="json", by_alias=True, exclude_none=True)
            if isinstance(msg, LLMMessage)
            else msg
            for msg in self.messages
        ]
        return payload


class LLMCompletionChoice(BaseModel):
    """Single completion choice in a non-streaming response."""

    index: int
    message: LLMMessage
    finish_reason: str | None = None


class LLMCompletion(BaseModel):
    """Normalized non-streaming completion response."""

    id: str | None = None
    model: str | None = None
    choices: list[LLMCompletionChoice]
    usage: LLMUsage | None = None
    provider_extensions: dict[str, Any] | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> LLMCompletion:
        """Normalize a provider payload into an ``LLMCompletion``."""
        choices: list[LLMCompletionChoice] = []

        for item in payload.get("choices", []):
            raw_message = item.get("message")
            if not isinstance(raw_message, dict):
                raw_message = {"role": "assistant", "content": ""}

            choices.append(
                LLMCompletionChoice(
                    index=item.get("index", len(choices)),
                    message=LLMMessage.model_validate(raw_message),
                    finish_reason=item.get("finish_reason"),
                )
            )

        return cls(
            id=payload.get("id"),
            model=payload.get("model"),
            choices=choices,
            usage=LLMUsage.from_payload(payload.get("usage")),
            provider_extensions=payload.get("provider_extensions"),
        )


class LLMStreamChoice(BaseModel):
    """Single streaming choice delta."""

    index: int
    delta: LLMMessage
    finish_reason: str | None = None


class LLMStreamChunk(BaseModel):
    """Normalized streaming chunk emitted by a provider."""

    id: str | None = None
    model: str | None = None
    choices: list[LLMStreamChoice]
    provider_extensions: dict[str, Any] | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> LLMStreamChunk:
        """Normalize a provider payload into an ``LLMStreamChunk``."""
        choices: list[LLMStreamChoice] = []

        for item in payload.get("choices", []):
            raw_delta = item.get("delta")
            if not isinstance(raw_delta, dict):
                raw_delta = {"role": "assistant", "content": ""}

            choices.append(
                LLMStreamChoice(
                    index=item.get("index", len(choices)),
                    delta=LLMMessage.model_validate(raw_delta),
                    finish_reason=item.get("finish_reason"),
                )
            )

        return cls(
            id=payload.get("id"),
            model=payload.get("model"),
            choices=choices,
            provider_extensions=payload.get("provider_extensions"),
        )
