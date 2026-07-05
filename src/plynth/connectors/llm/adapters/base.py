"""Base adapter contracts and default implementations for LLM providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Protocol

from plynth.connectors.llm.models import (
    LLMGenerateRequest,
    LLMStreamChunk,
)


class LLMRequestAdapter(Protocol):
    """Contract for mapping neutral requests to provider payloads."""

    def to_provider_payload(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Map neutral request to provider-specific request payload."""
        raise NotImplementedError


class LLMCompletionAdapter(Protocol):
    """Contract for mapping provider responses to neutral completion payloads."""

    def to_neutral_completion_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Map provider completion payload to neutral completion payload."""
        raise NotImplementedError


class LLMStreamAdapter(Protocol):
    """Contract for mapping one provider stream event payload to chunk."""

    def parse_event_payload(self, payload_line: str) -> LLMStreamChunk | None:
        """Parse one provider stream event payload."""


class DefaultLLMRequestAdapter:
    """Default request adapter using the neutral request wire shape."""

    def to_provider_payload(
        self,
        request: LLMGenerateRequest,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Serialize request using neutral keys only."""
        if stream:
            return request.with_stream(True).to_payload()
        return request.to_payload()


class DefaultLLMCompletionAdapter:
    """Default completion adapter for already-neutral payloads."""

    def to_neutral_completion_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return payload unchanged when provider shape is already neutral."""
        return payload


class DefaultLLMStreamAdapter:
    """Default stream adapter for JSON event payloads."""

    def parse_event_payload(self, payload_line: str) -> LLMStreamChunk | None:
        """Parse one JSON stream payload into a normalized chunk."""
        stripped = payload_line.strip()
        if not stripped or stripped == "[DONE]":
            return None

        try:
            payload = json.loads(stripped)
        except JSONDecodeError as exc:
            raise ValueError("Failed to parse LLM stream event payload") from exc

        if not isinstance(payload, dict):
            raise ValueError("Expected JSON object payload for stream event")

        return LLMStreamChunk.from_payload(payload)


@dataclass(slots=True)
class LLMAdapterSet:
    """Grouped adapters used by LLM services."""

    request_adapter: LLMRequestAdapter
    completion_adapter: LLMCompletionAdapter
    stream_adapter: LLMStreamAdapter


def build_default_adapter_set() -> LLMAdapterSet:
    """Return default adapter set for neutral provider payloads."""
    return LLMAdapterSet(
        request_adapter=DefaultLLMRequestAdapter(),
        completion_adapter=DefaultLLMCompletionAdapter(),
        stream_adapter=DefaultLLMStreamAdapter(),
    )
