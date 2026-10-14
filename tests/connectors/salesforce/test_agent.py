"""Tests for SalesforceAgentService and AsyncSalesforceAgentService."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

from plynt.base.response import AsyncStreamingResponse, StreamingResponse
from plynt.connectors.salesforce.agent import (
    AsyncSalesforceAgentService,
    SalesforceAgentService,
)
from plynt.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynt.connectors.salesforce.models import (
    AgentFeedbackRequest,
    AgentMessageRequest,
    AgentMessageResponse,
    AgentSession,
    AgentSessionEndAck,
    AgentSessionStartRequest,
    FeedbackAck,
)
from plynt.http.client import APIClient, AsyncAPIClient
from plynt.http.renderer import JSONRenderer
from tests.conftest import MockAsyncTransport, MockSyncTransport
from tests.connectors.salesforce.conftest import DUMMY_INSTANCE_URL

_JSON_RENDERER = JSONRenderer()


def _json_bytes(data: Any) -> bytes:
    """Render arbitrary data to JSON bytes using the shared JSON renderer."""
    return _JSON_RENDERER.render(data)


def _make_service(
    *,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[SalesforceAgentService, MockSyncTransport]:
    """Build a SalesforceAgentService backed by a sync mock transport."""
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
    return SalesforceAgentService(client), transport


def _make_async_service(
    *,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[AsyncSalesforceAgentService, MockAsyncTransport]:
    """Build an AsyncSalesforceAgentService backed by an async mock transport."""
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
    return AsyncSalesforceAgentService(client), transport


class TestSalesforceAgentService:
    """Tests for SalesforceAgentService."""

    def test_start_session_posts_expected_payload(self) -> None:
        """start_session posts to /sessions and returns typed session model."""
        payload = {"sessionId": "sess-1", "agentId": "agent-1", "status": "active"}
        svc, transport = _make_service(content=_json_bytes(payload))

        result = svc.start_session("agent-1", context={"locale": "en"})

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith("/einstein/ai-agent/v1/sessions")
        assert json.loads(sent.content or b"{}") == {
            "agentId": "agent-1",
            "context": {"locale": "en"},
        }
        assert isinstance(result, AgentSession)
        assert result.session_id == "sess-1"

    def test_send_message_posts_expected_payload(self) -> None:
        """send_message posts text and metadata to session message endpoint."""
        payload = {"sessionId": "sess-1", "messageId": "msg-1", "outputText": "hi"}
        svc, transport = _make_service(content=_json_bytes(payload))

        result = svc.send_message("sess-1", "hello", metadata={"channel": "web"})

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/einstein/ai-agent/v1/sessions/sess-1/messages")
        assert json.loads(sent.content or b"{}") == {
            "text": "hello",
            "metadata": {"channel": "web"},
        }
        assert isinstance(result, AgentMessageResponse)
        assert result.message_id == "msg-1"

    def test_send_message_streaming_uses_stream_api(self) -> None:
        """send_message_streaming returns a StreamingResponse."""
        svc, transport = _make_service()
        streaming = StreamingResponse(
            status_code=200, headers={}, content=b"", _raw=MagicMock()
        )
        transport.send.return_value = streaming

        result = svc.send_message_streaming("sess-1", "hello")

        sent = transport.send.call_args[0][0]
        assert sent.stream is True
        assert sent.url.endswith("/einstein/ai-agent/v1/sessions/sess-1/messages")
        assert isinstance(result, StreamingResponse)

    def test_end_session_calls_delete_and_returns_ack(self) -> None:
        """end_session calls DELETE and parses AgentSessionEndAck."""
        payload = {"sessionId": "sess-1", "ended": True}
        svc, transport = _make_service(content=_json_bytes(payload))

        result = svc.end_session("sess-1")

        sent = transport.send.call_args[0][0]
        assert sent.method == "DELETE"
        assert sent.url.endswith("/einstein/ai-agent/v1/sessions/sess-1")
        assert isinstance(result, AgentSessionEndAck)
        assert result.ended is True

    def test_submit_feedback_posts_expected_payload(self) -> None:
        """submit_feedback posts rating metadata and parses FeedbackAck."""
        payload = {"success": True, "requestId": "fb-1"}
        svc, transport = _make_service(content=_json_bytes(payload))

        result = svc.submit_feedback(
            "sess-1",
            5,
            message_id="msg-1",
            comment="helpful",
        )

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/einstein/ai-agent/v1/feedback")
        assert json.loads(sent.content or b"{}") == {
            "sessionId": "sess-1",
            "messageId": "msg-1",
            "rating": 5,
            "comment": "helpful",
        }
        assert isinstance(result, FeedbackAck)

    def test_facade_agent_returns_service(self) -> None:
        """The sync facade returns a SalesforceAgentService instance."""
        transport = MockSyncTransport(content=b"{}")
        client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        facade = SalesforceAPIFacade(client)

        svc = facade.agent()

        assert isinstance(svc, SalesforceAgentService)


class TestAsyncSalesforceAgentService:
    """Tests for AsyncSalesforceAgentService."""

    async def test_start_session_posts_expected_payload(self) -> None:
        """Async start_session posts expected payload and parses model."""
        payload = {"sessionId": "sess-2", "agentId": "agent-1", "status": "active"}
        svc, transport = _make_async_service(content=_json_bytes(payload))

        result = await svc.start_session("agent-1")

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith("/einstein/ai-agent/v1/sessions")
        assert json.loads(sent.content or b"{}") == {"agentId": "agent-1"}
        assert isinstance(result, AgentSession)

    async def test_send_message_posts_expected_payload(self) -> None:
        """Async send_message posts text payload and parses model."""
        payload = {"sessionId": "sess-2", "messageId": "msg-2", "outputText": "done"}
        svc, transport = _make_async_service(content=_json_bytes(payload))

        result = await svc.send_message("sess-2", "hello")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/einstein/ai-agent/v1/sessions/sess-2/messages")
        assert json.loads(sent.content or b"{}") == {"text": "hello"}
        assert isinstance(result, AgentMessageResponse)

    async def test_send_message_streaming_uses_stream_api(self) -> None:
        """Async send_message_streaming returns AsyncStreamingResponse."""
        svc, transport = _make_async_service()
        raw = MagicMock()
        raw.aiter_lines.return_value = iter(())
        streaming = AsyncStreamingResponse(
            status_code=200, headers={}, content=b"", _raw=raw
        )
        transport.send.return_value = streaming

        result = await svc.send_message_streaming("sess-2", "hello")

        sent = transport.send.call_args[0][0]
        assert sent.stream is True
        assert sent.url.endswith("/einstein/ai-agent/v1/sessions/sess-2/messages")
        assert isinstance(result, AsyncStreamingResponse)

    async def test_end_session_calls_delete_and_returns_ack(self) -> None:
        """Async end_session calls DELETE and parses ack model."""
        payload = {"sessionId": "sess-2", "ended": True}
        svc, transport = _make_async_service(content=_json_bytes(payload))

        result = await svc.end_session("sess-2")

        sent = transport.send.call_args[0][0]
        assert sent.method == "DELETE"
        assert sent.url.endswith("/einstein/ai-agent/v1/sessions/sess-2")
        assert isinstance(result, AgentSessionEndAck)

    async def test_submit_feedback_posts_expected_payload(self) -> None:
        """Async submit_feedback posts payload and parses FeedbackAck."""
        payload = {"success": True, "requestId": "fb-2"}
        svc, transport = _make_async_service(content=_json_bytes(payload))

        result = await svc.submit_feedback("sess-2", 4, comment="ok")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/einstein/ai-agent/v1/feedback")
        assert json.loads(sent.content or b"{}") == {
            "sessionId": "sess-2",
            "rating": 4,
            "comment": "ok",
        }
        assert isinstance(result, FeedbackAck)

    async def test_facade_agent_returns_service(self) -> None:
        """The async facade returns an AsyncSalesforceAgentService instance."""
        transport = MockAsyncTransport(content=b"{}")
        client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        facade = AsyncSalesforceAPIFacade(client)

        svc = facade.agent()

        assert isinstance(svc, AsyncSalesforceAgentService)


class TestAgentApiRequestModels:
    """Tests for typed request payload schemas used by Agent API services."""

    def test_start_session_request_excludes_empty_context(self) -> None:
        """to_payload omits context when no context is provided."""
        request = AgentSessionStartRequest(agent_id="agent-1")

        assert request.to_payload() == {"agentId": "agent-1"}

    def test_message_request_serializes_metadata(self) -> None:
        """to_payload keeps text and metadata fields for message posting."""
        request = AgentMessageRequest(text="Hello", metadata={"channel": "web"})

        assert request.to_payload() == {
            "text": "Hello",
            "metadata": {"channel": "web"},
        }

    def test_feedback_request_excludes_optional_none_fields(self) -> None:
        """to_payload excludes message_id and comment when omitted."""
        request = AgentFeedbackRequest(session_id="sess-1", rating=5)

        assert request.to_payload() == {
            "sessionId": "sess-1",
            "rating": 5,
        }
