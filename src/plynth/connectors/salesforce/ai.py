"""Salesforce Models API service.

Provides sync and async wrappers for Salesforce-hosted model inference
endpoints. These services keep provider-specific payload shapes in the
Salesforce connector while relying on shared plynth transport primitives.
"""

from __future__ import annotations

from typing import Any

from plynth.base.response import AsyncStreamingResponse, StreamingResponse
from plynth.connectors.salesforce.models import (
    ChatCompletionResponse,
    ChatMessage,
    EmbeddingResponse,
    FeedbackAck,
    ModelsChatGenerationRequest,
    ModelsEmbeddingRequest,
    ModelsFeedbackRequest,
    ModelsTextGenerationRequest,
    TextGenerationResponse,
)
from plynth.connectors.salesforce.renderer import SalesforceRenderer
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import Renderer
from plynth.http.service import APIService, AsyncAPIService

__all__ = [
    "AsyncSalesforceModelsService",
    "SalesforceModelsService",
]

_MODELS_API_BASE = "/einstein/platform/v1"


class SalesforceModelsService(APIService):
    """Sync service for Salesforce Models API endpoints."""

    def __init__(
        self,
        client: APIClient,
        *,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize SalesforceModelsService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())

    def generate_chat(
        self,
        messages: list[dict[str, Any] | ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        metadata: dict[str, str] | None = None,
    ) -> ChatCompletionResponse | StreamingResponse:
        """Generate a chat completion from the Models API.

        Args:
            messages: Ordered chat messages as provider-compatible objects.
            model: Optional model identifier.
            temperature: Optional sampling temperature.
            max_tokens: Optional generation token cap.
            stream: When ``True``, returns a ``StreamingResponse``.
            metadata: Optional metadata to attach to the request.

        """
        payload = ModelsChatGenerationRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            metadata=metadata,
        ).to_payload()
        body = self._renderer.render(payload)
        if stream:
            return self._client.stream(
                "POST",
                f"{_MODELS_API_BASE}/chat-generations",
                content=body,
            )
        resp = self._client.post(
            f"{_MODELS_API_BASE}/chat-generations",
            content=body,
        )
        return ChatCompletionResponse.model_validate_json(resp.content)

    def generate_text(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> TextGenerationResponse:
        """Generate text from the Models API."""
        payload = ModelsTextGenerationRequest(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ).to_payload()
        resp = self._client.post(
            f"{_MODELS_API_BASE}/generations",
            content=self._renderer.render(payload),
        )
        return TextGenerationResponse.model_validate_json(resp.content)

    def generate_embeddings(
        self,
        input_text: str | list[str],
        *,
        model: str | None = None,
    ) -> EmbeddingResponse:
        """Generate embeddings from the Models API."""
        payload = ModelsEmbeddingRequest.model_validate(
            {
                "input_text": input_text,
                "model": model,
            }
        ).to_payload()
        resp = self._client.post(
            f"{_MODELS_API_BASE}/embeddings",
            content=self._renderer.render(payload),
        )
        return EmbeddingResponse.model_validate_json(resp.content)

    def submit_feedback(
        self,
        request_id: str,
        rating: int,
        *,
        comment: str | None = None,
    ) -> FeedbackAck:
        """Submit feedback for a previously generated model response."""
        payload = ModelsFeedbackRequest(
            request_id=request_id,
            rating=rating,
            comment=comment,
        ).to_payload()
        resp = self._client.post(
            f"{_MODELS_API_BASE}/feedback",
            content=self._renderer.render(payload),
        )
        return FeedbackAck.model_validate_json(resp.content)


class AsyncSalesforceModelsService(AsyncAPIService):
    """Async service for Salesforce Models API endpoints."""

    def __init__(
        self,
        client: AsyncAPIClient,
        *,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncSalesforceModelsService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())

    async def generate_chat(
        self,
        messages: list[dict[str, Any] | ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        metadata: dict[str, str] | None = None,
    ) -> ChatCompletionResponse | AsyncStreamingResponse:
        """Generate a chat completion from the Models API."""
        payload = ModelsChatGenerationRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            metadata=metadata,
        ).to_payload()
        body = self._renderer.render(payload)
        if stream:
            return await self._client.stream(
                "POST",
                f"{_MODELS_API_BASE}/chat-generations",
                content=body,
            )
        resp = await self._client.post(
            f"{_MODELS_API_BASE}/chat-generations",
            content=body,
        )
        return ChatCompletionResponse.model_validate_json(resp.content)

    async def generate_text(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> TextGenerationResponse:
        """Generate text from the Models API."""
        payload = ModelsTextGenerationRequest(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ).to_payload()
        resp = await self._client.post(
            f"{_MODELS_API_BASE}/generations",
            content=self._renderer.render(payload),
        )
        return TextGenerationResponse.model_validate_json(resp.content)

    async def generate_embeddings(
        self,
        input_text: str | list[str],
        *,
        model: str | None = None,
    ) -> EmbeddingResponse:
        """Generate embeddings from the Models API."""
        payload = ModelsEmbeddingRequest.model_validate(
            {
                "input_text": input_text,
                "model": model,
            }
        ).to_payload()
        resp = await self._client.post(
            f"{_MODELS_API_BASE}/embeddings",
            content=self._renderer.render(payload),
        )
        return EmbeddingResponse.model_validate_json(resp.content)

    async def submit_feedback(
        self,
        request_id: str,
        rating: int,
        *,
        comment: str | None = None,
    ) -> FeedbackAck:
        """Submit feedback for a previously generated model response."""
        payload = ModelsFeedbackRequest(
            request_id=request_id,
            rating=rating,
            comment=comment,
        ).to_payload()
        resp = await self._client.post(
            f"{_MODELS_API_BASE}/feedback",
            content=self._renderer.render(payload),
        )
        return FeedbackAck.model_validate_json(resp.content)
