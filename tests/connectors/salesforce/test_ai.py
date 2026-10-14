"""Tests for SalesforceModelsService and AsyncSalesforceModelsService."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from plynt.base.response import AsyncStreamingResponse, StreamingResponse
from plynt.connectors.salesforce.ai import (
    AsyncSalesforceModelsService,
    SalesforceModelsService,
)
from plynt.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynt.connectors.salesforce.models import (
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
from plynt.http.client import APIClient, AsyncAPIClient
from plynt.http.renderer import JSONRenderer
from tests.conftest import MockAsyncTransport, MockSyncTransport
from tests.connectors.salesforce.conftest import DUMMY_INSTANCE_URL

_JSON_RENDERER = JSONRenderer()
REPO_ROOT = Path(__file__).resolve().parents[3]
CONNECTORS_ROOT = REPO_ROOT / "src" / "plynt" / "connectors"
SALESFORCE_ROOT = CONNECTORS_ROOT / "salesforce"
LLM_ROOT = CONNECTORS_ROOT / "llm"


def _json_bytes(data: Any) -> bytes:
    """Render arbitrary data to JSON bytes using the shared JSON renderer."""
    return _JSON_RENDERER.render(data)


def _iter_python_files(root: Path) -> list[Path]:
    """Return all Python source files below the given root."""
    return sorted(
        path for path in root.rglob("*.py") if "__pycache__" not in path.parts
    )


def _imported_modules(path: Path) -> set[str]:
    """Return imported module names from a Python source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
            continue

        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)

    return modules


def _imports_connector(root: Path, forbidden_prefix: str) -> list[str]:
    """Return import violations for modules below a connector root."""
    violations: list[str] = []

    for path in _iter_python_files(root):
        for module in _imported_modules(path):
            if module == forbidden_prefix or module.startswith(f"{forbidden_prefix}."):
                violations.append(f"{path.relative_to(REPO_ROOT)} imports {module}")

    return violations


def _make_service(
    *,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[SalesforceModelsService, MockSyncTransport]:
    """Build a SalesforceModelsService backed by a sync mock transport."""
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
    return SalesforceModelsService(client), transport


def _make_async_service(
    *,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[AsyncSalesforceModelsService, MockAsyncTransport]:
    """Build an AsyncSalesforceModelsService backed by an async mock transport."""
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
    return AsyncSalesforceModelsService(client), transport


class TestSalesforceModelsService:
    """Tests for SalesforceModelsService."""

    def test_generate_chat_posts_expected_payload(self) -> None:
        """generate_chat posts to the expected endpoint with provided options."""
        payload = {
            "id": "chat-1",
            "model": "sf-model",
            "choices": [{"message": {"content": "hello"}}],
        }
        svc, transport = _make_service(content=_json_bytes(payload))

        result = svc.generate_chat(
            [{"role": "user", "content": "Hello"}],
            model="sf-model",
            temperature=0.2,
            max_tokens=64,
            metadata={"tenant": "acme"},
        )

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith("/einstein/platform/v1/chat-generations")
        assert json.loads(sent.content or b"{}") == {
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "sf-model",
            "temperature": 0.2,
            "max_tokens": 64,
            "stream": False,
            "metadata": {"tenant": "acme"},
        }
        assert isinstance(result, ChatCompletionResponse)
        assert result.id == "chat-1"

    def test_generate_chat_streaming_uses_stream_api(self) -> None:
        """generate_chat returns a StreamingResponse when stream=True."""
        svc, transport = _make_service()
        streaming = StreamingResponse(
            status_code=200, headers={}, content=b"", _raw=MagicMock()
        )
        transport.send.return_value = streaming

        result = svc.generate_chat(
            [{"role": "user", "content": "Hello"}],
            stream=True,
        )

        sent = transport.send.call_args[0][0]
        assert sent.stream is True
        assert sent.url.endswith("/einstein/platform/v1/chat-generations")
        assert isinstance(result, StreamingResponse)

    def test_generate_text_returns_typed_model(self) -> None:
        """generate_text parses a typed TextGenerationResponse."""
        payload = {"id": "txt-1", "model": "sf-model", "text": "world"}
        svc, transport = _make_service(content=_json_bytes(payload))

        result = svc.generate_text("Say hi", model="sf-model")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/einstein/platform/v1/generations")
        assert json.loads(sent.content or b"{}") == {
            "prompt": "Say hi",
            "model": "sf-model",
        }
        assert isinstance(result, TextGenerationResponse)
        assert result.text == "world"

    def test_generate_embeddings_returns_typed_model(self) -> None:
        """generate_embeddings parses a typed EmbeddingResponse."""
        payload = {"model": "embed-1", "data": [{"index": 0, "embedding": [0.1, 0.2]}]}
        svc, transport = _make_service(content=_json_bytes(payload))

        result = svc.generate_embeddings(["a", "b"], model="embed-1")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/einstein/platform/v1/embeddings")
        assert json.loads(sent.content or b"{}") == {
            "input": ["a", "b"],
            "model": "embed-1",
        }
        assert isinstance(result, EmbeddingResponse)
        assert result.model == "embed-1"

    def test_submit_feedback_returns_ack(self) -> None:
        """submit_feedback parses a typed FeedbackAck model."""
        payload = {"success": True, "requestId": "req-1"}
        svc, transport = _make_service(content=_json_bytes(payload))

        result = svc.submit_feedback("req-1", 5, comment="great")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/einstein/platform/v1/feedback")
        assert json.loads(sent.content or b"{}") == {
            "requestId": "req-1",
            "rating": 5,
            "comment": "great",
        }
        assert isinstance(result, FeedbackAck)
        assert result.request_id == "req-1"

    def test_facade_models_returns_service(self) -> None:
        """The sync facade returns a SalesforceModelsService instance."""
        transport = MockSyncTransport(content=b"{}")
        client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        facade = SalesforceAPIFacade(client)

        svc = facade.models()

        assert isinstance(svc, SalesforceModelsService)


class TestAsyncSalesforceModelsService:
    """Tests for AsyncSalesforceModelsService."""

    async def test_generate_chat_posts_expected_payload(self) -> None:
        """Async generate_chat posts to expected endpoint."""
        payload = {
            "id": "chat-async-1",
            "model": "sf-model",
            "choices": [{"message": {"content": "hello"}}],
        }
        svc, transport = _make_async_service(content=_json_bytes(payload))

        result = await svc.generate_chat(
            [{"role": "user", "content": "Hello"}],
            model="sf-model",
        )

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith("/einstein/platform/v1/chat-generations")
        assert json.loads(sent.content or b"{}") == {
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "sf-model",
            "stream": False,
        }
        assert isinstance(result, ChatCompletionResponse)
        assert result.id == "chat-async-1"

    async def test_generate_chat_streaming_uses_stream_api(self) -> None:
        """Async generate_chat returns AsyncStreamingResponse when stream=True."""
        svc, transport = _make_async_service()
        raw = MagicMock()
        raw.aiter_lines.return_value = iter(())
        streaming = AsyncStreamingResponse(
            status_code=200, headers={}, content=b"", _raw=raw
        )
        transport.send.return_value = streaming

        result = await svc.generate_chat(
            [{"role": "user", "content": "Hello"}],
            stream=True,
        )

        sent = transport.send.call_args[0][0]
        assert sent.stream is True
        assert sent.url.endswith("/einstein/platform/v1/chat-generations")
        assert isinstance(result, AsyncStreamingResponse)

    async def test_generate_text_returns_typed_model(self) -> None:
        """Async generate_text parses a typed TextGenerationResponse."""
        payload = {"id": "txt-async-1", "model": "sf-model", "text": "world"}
        svc, transport = _make_async_service(content=_json_bytes(payload))

        result = await svc.generate_text("Say hi", model="sf-model")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/einstein/platform/v1/generations")
        assert isinstance(result, TextGenerationResponse)
        assert result.text == "world"

    async def test_generate_embeddings_returns_typed_model(self) -> None:
        """Async generate_embeddings parses a typed EmbeddingResponse."""
        payload = {"model": "embed-1", "data": [{"index": 0, "embedding": [0.1, 0.2]}]}
        svc, transport = _make_async_service(content=_json_bytes(payload))

        result = await svc.generate_embeddings("hello", model="embed-1")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/einstein/platform/v1/embeddings")
        assert json.loads(sent.content or b"{}") == {
            "input": "hello",
            "model": "embed-1",
        }
        assert isinstance(result, EmbeddingResponse)

    async def test_submit_feedback_returns_ack(self) -> None:
        """Async submit_feedback parses a typed FeedbackAck model."""
        payload = {"success": True, "requestId": "req-2"}
        svc, transport = _make_async_service(content=_json_bytes(payload))

        result = await svc.submit_feedback("req-2", 4)

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/einstein/platform/v1/feedback")
        assert json.loads(sent.content or b"{}") == {
            "requestId": "req-2",
            "rating": 4,
        }
        assert isinstance(result, FeedbackAck)

    async def test_facade_models_returns_service(self) -> None:
        """The async facade returns an AsyncSalesforceModelsService instance."""
        transport = MockAsyncTransport(content=b"{}")
        client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        facade = AsyncSalesforceAPIFacade(client)

        svc = facade.models()

        assert isinstance(svc, AsyncSalesforceModelsService)


class TestAIConnectorBoundaries:
    """Guard independent evolution of Salesforce and generic AI connectors."""

    def test_salesforce_connector_does_not_import_llm_connector(self) -> None:
        """Keep Salesforce AI services independent from a generic LLM connector."""
        violations = _imports_connector(SALESFORCE_ROOT, "plynt.connectors.llm")

        assert violations == []

    def test_llm_connector_does_not_import_salesforce_connector(self) -> None:
        """Keep a future generic LLM connector independent from Salesforce."""
        if not LLM_ROOT.exists():
            pytest.skip("plynt.connectors.llm does not exist yet")

        violations = _imports_connector(LLM_ROOT, "plynt.connectors.salesforce")

        assert violations == []


class TestModelsApiRequestModels:
    """Tests for typed request payload schemas used by Models API services."""

    def test_chat_generation_request_serializes_typed_messages(self) -> None:
        """to_payload serializes ChatMessage items to provider-compatible dicts."""
        request = ModelsChatGenerationRequest(
            messages=[
                ChatMessage(role="system", content="You are helpful"),
                {"role": "user", "content": "Hello"},
            ],
            model="sf-model",
            stream=True,
        )

        assert request.to_payload() == {
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
            ],
            "model": "sf-model",
            "stream": True,
        }

    def test_embedding_request_serializes_input_alias(self) -> None:
        """to_payload maps input_text to the wire-format input field."""
        request = ModelsEmbeddingRequest(input_text=["a", "b"], model="embed-1")

        assert request.to_payload() == {
            "input": ["a", "b"],
            "model": "embed-1",
        }

    def test_text_and_feedback_requests_exclude_none_values(self) -> None:
        """to_payload excludes optional fields when they are not provided."""
        text_request = ModelsTextGenerationRequest(prompt="Hello", model="sf-model")
        feedback_request = ModelsFeedbackRequest(request_id="req-1", rating=4)

        assert text_request.to_payload() == {
            "prompt": "Hello",
            "model": "sf-model",
        }
        assert feedback_request.to_payload() == {
            "requestId": "req-1",
            "rating": 4,
        }
