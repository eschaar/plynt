"""Salesforce Agent API service.

Provides sync and async wrappers around Salesforce agent session and
messaging endpoints.
"""

from __future__ import annotations

from plynt.base.response import AsyncStreamingResponse, StreamingResponse
from plynt.connectors.salesforce.models import (
    AgentFeedbackRequest,
    AgentMessageRequest,
    AgentMessageResponse,
    AgentSession,
    AgentSessionEndAck,
    AgentSessionStartRequest,
    FeedbackAck,
)
from plynt.connectors.salesforce.renderer import SalesforceRenderer
from plynt.http.client import APIClient, AsyncAPIClient
from plynt.http.renderer import Renderer
from plynt.http.service import APIService, AsyncAPIService

__all__ = [
    "AsyncSalesforceAgentService",
    "SalesforceAgentService",
]

_AGENT_API_BASE = "/einstein/ai-agent/v1"


class SalesforceAgentService(APIService):
    """Sync service for Salesforce Agent API endpoints."""

    def __init__(
        self,
        client: APIClient,
        *,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize SalesforceAgentService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())

    def start_session(
        self,
        agent_id: str,
        *,
        context: dict[str, str] | None = None,
    ) -> AgentSession:
        """Start a new agent session."""
        payload = AgentSessionStartRequest(
            agent_id=agent_id,
            context=context,
        ).to_payload()
        resp = self._client.post(
            f"{_AGENT_API_BASE}/sessions",
            content=self._renderer.render(payload),
        )
        return AgentSession.model_validate_json(resp.content)

    def send_message(
        self,
        session_id: str,
        text: str,
        *,
        metadata: dict[str, str] | None = None,
    ) -> AgentMessageResponse:
        """Send a synchronous message to an active agent session."""
        payload = AgentMessageRequest(text=text, metadata=metadata).to_payload()
        resp = self._client.post(
            f"{_AGENT_API_BASE}/sessions/{session_id}/messages",
            content=self._renderer.render(payload),
        )
        return AgentMessageResponse.model_validate_json(resp.content)

    def send_message_streaming(
        self,
        session_id: str,
        text: str,
        *,
        metadata: dict[str, str] | None = None,
    ) -> StreamingResponse:
        """Send a message and stream incremental agent output."""
        payload = AgentMessageRequest(text=text, metadata=metadata).to_payload()
        return self._client.stream(
            "POST",
            f"{_AGENT_API_BASE}/sessions/{session_id}/messages",
            content=self._renderer.render(payload),
        )

    def end_session(self, session_id: str) -> AgentSessionEndAck:
        """End an active session and return the server acknowledgement."""
        resp = self._client.delete(f"{_AGENT_API_BASE}/sessions/{session_id}")
        return AgentSessionEndAck.model_validate_json(resp.content)

    def submit_feedback(
        self,
        session_id: str,
        rating: int,
        *,
        message_id: str | None = None,
        comment: str | None = None,
    ) -> FeedbackAck:
        """Submit feedback for an agent response."""
        payload = AgentFeedbackRequest(
            session_id=session_id,
            message_id=message_id,
            rating=rating,
            comment=comment,
        ).to_payload()
        resp = self._client.post(
            f"{_AGENT_API_BASE}/feedback",
            content=self._renderer.render(payload),
        )
        return FeedbackAck.model_validate_json(resp.content)


class AsyncSalesforceAgentService(AsyncAPIService):
    """Async service for Salesforce Agent API endpoints."""

    def __init__(
        self,
        client: AsyncAPIClient,
        *,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncSalesforceAgentService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())

    async def start_session(
        self,
        agent_id: str,
        *,
        context: dict[str, str] | None = None,
    ) -> AgentSession:
        """Start a new agent session."""
        payload = AgentSessionStartRequest(
            agent_id=agent_id,
            context=context,
        ).to_payload()
        resp = await self._client.post(
            f"{_AGENT_API_BASE}/sessions",
            content=self._renderer.render(payload),
        )
        return AgentSession.model_validate_json(resp.content)

    async def send_message(
        self,
        session_id: str,
        text: str,
        *,
        metadata: dict[str, str] | None = None,
    ) -> AgentMessageResponse:
        """Send a synchronous message to an active agent session."""
        payload = AgentMessageRequest(text=text, metadata=metadata).to_payload()
        resp = await self._client.post(
            f"{_AGENT_API_BASE}/sessions/{session_id}/messages",
            content=self._renderer.render(payload),
        )
        return AgentMessageResponse.model_validate_json(resp.content)

    async def send_message_streaming(
        self,
        session_id: str,
        text: str,
        *,
        metadata: dict[str, str] | None = None,
    ) -> AsyncStreamingResponse:
        """Send a message and stream incremental agent output."""
        payload = AgentMessageRequest(text=text, metadata=metadata).to_payload()
        return await self._client.stream(
            "POST",
            f"{_AGENT_API_BASE}/sessions/{session_id}/messages",
            content=self._renderer.render(payload),
        )

    async def end_session(self, session_id: str) -> AgentSessionEndAck:
        """End an active session and return the server acknowledgement."""
        resp = await self._client.delete(f"{_AGENT_API_BASE}/sessions/{session_id}")
        return AgentSessionEndAck.model_validate_json(resp.content)

    async def submit_feedback(
        self,
        session_id: str,
        rating: int,
        *,
        message_id: str | None = None,
        comment: str | None = None,
    ) -> FeedbackAck:
        """Submit feedback for an agent response."""
        payload = AgentFeedbackRequest(
            session_id=session_id,
            message_id=message_id,
            rating=rating,
            comment=comment,
        ).to_payload()
        resp = await self._client.post(
            f"{_AGENT_API_BASE}/feedback",
            content=self._renderer.render(payload),
        )
        return FeedbackAck.model_validate_json(resp.content)
