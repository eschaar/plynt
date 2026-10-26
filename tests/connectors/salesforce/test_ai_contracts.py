"""Verify AI service contracts through the real HTTP and response layers"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass

import httpx2 as httpx
import pytest
from pydantic import BaseModel, ValidationError

from plynt.base.errors import StreamInterruptedError
from plynt.base.response import AsyncStreamingResponse, StreamingResponse
from plynt.connectors.salesforce.agent import (
    AsyncSalesforceAgentService,
    SalesforceAgentService,
)
from plynt.connectors.salesforce.ai import (
    AsyncSalesforceModelsService,
    SalesforceModelsService,
)
from plynt.connectors.salesforce.auth import (
    AsyncSalesforceSessionAuthMiddleware,
    SalesforceSessionAuthMiddleware,
)
from plynt.connectors.salesforce.client import (
    AsyncSalesforceAPIClient,
    SalesforceAPIClient,
)
from plynt.connectors.salesforce.errors import SalesforceValidationError
from plynt.connectors.salesforce.models import (
    AgentFeedbackRequest,
    ModelsFeedbackRequest,
)
from plynt.http.policies import HttpRetryPolicy
from plynt.http.transport import HttpxAsyncTransport, HttpxSyncTransport
from plynt.middleware.retry import AsyncRetryMiddleware, RetryMiddleware
from tests.connectors.salesforce.conftest import DUMMY_ACCESS_TOKEN, DUMMY_INSTANCE_URL


def _sync_client(transport: HttpxSyncTransport) -> SalesforceAPIClient:
    """Build a client with an externally managed test session"""
    return SalesforceAPIClient(
        auth=SalesforceSessionAuthMiddleware(
            access_token=DUMMY_ACCESS_TOKEN, instance_url=DUMMY_INSTANCE_URL
        ),
        transport=transport,
    )


def _async_client(transport: HttpxAsyncTransport) -> AsyncSalesforceAPIClient:
    """Build an async client with an externally managed test session"""
    return AsyncSalesforceAPIClient(
        auth=AsyncSalesforceSessionAuthMiddleware(
            access_token=DUMMY_ACCESS_TOKEN, instance_url=DUMMY_INSTANCE_URL
        ),
        transport=transport,
    )


@dataclass
class _ContractCase:
    name: str
    sync_call: Callable[
        [SalesforceModelsService, SalesforceAgentService],
        BaseModel | StreamingResponse,
    ]
    async_call: Callable[
        [AsyncSalesforceModelsService, AsyncSalesforceAgentService],
        Awaitable[BaseModel | AsyncStreamingResponse],
    ]
    path: str
    payload: dict[str, object] | None
    response: dict[str, object]
    method: str = "POST"


_CASES = [
    _ContractCase(
        "chat",
        lambda models, _agent: models.generate_chat(
            [{"role": "user", "content": "hello"}], model="test-model"
        ),
        lambda models, _agent: models.generate_chat(
            [{"role": "user", "content": "hello"}], model="test-model"
        ),
        "/einstein/platform/v1/chat-generations",
        {
            "messages": [{"role": "user", "content": "hello"}],
            "model": "test-model",
            "stream": False,
        },
        {"id": "chat-1", "choices": [{"message": {"content": "hello"}}]},
    ),
    _ContractCase(
        "text",
        lambda models, _agent: models.generate_text(
            "hello", temperature=0.2, max_tokens=8
        ),
        lambda models, _agent: models.generate_text(
            "hello", temperature=0.2, max_tokens=8
        ),
        "/einstein/platform/v1/generations",
        {"prompt": "hello", "temperature": 0.2, "max_tokens": 8},
        {"id": "text-1", "text": "hello"},
    ),
    _ContractCase(
        "embeddings",
        lambda models, _agent: models.generate_embeddings(["hello"]),
        lambda models, _agent: models.generate_embeddings(["hello"]),
        "/einstein/platform/v1/embeddings",
        {"input": ["hello"]},
        {"model": "embed-1", "data": [{"index": 0, "embedding": [0.1, 0.2]}]},
    ),
    _ContractCase(
        "models-feedback",
        lambda models, _agent: models.submit_feedback(
            "request-1", 5, comment="helpful"
        ),
        lambda models, _agent: models.submit_feedback(
            "request-1", 5, comment="helpful"
        ),
        "/einstein/platform/v1/feedback",
        {"requestId": "request-1", "rating": 5, "comment": "helpful"},
        {"success": True, "requestId": "request-1"},
    ),
    _ContractCase(
        "start-session",
        lambda _models, agent: agent.start_session("agent-1", context={"locale": "en"}),
        lambda _models, agent: agent.start_session("agent-1", context={"locale": "en"}),
        "/einstein/ai-agent/v1/sessions",
        {"agentId": "agent-1", "context": {"locale": "en"}},
        {"sessionId": "session-1", "agentId": "agent-1", "status": "active"},
    ),
    _ContractCase(
        "message",
        lambda _models, agent: agent.send_message(
            "session-1", "hello", metadata={"channel": "web"}
        ),
        lambda _models, agent: agent.send_message(
            "session-1", "hello", metadata={"channel": "web"}
        ),
        "/einstein/ai-agent/v1/sessions/session-1/messages",
        {"text": "hello", "metadata": {"channel": "web"}},
        {"sessionId": "session-1", "messageId": "message-1", "outputText": "hello"},
    ),
    _ContractCase(
        "end-session",
        lambda _models, agent: agent.end_session("session-1"),
        lambda _models, agent: agent.end_session("session-1"),
        "/einstein/ai-agent/v1/sessions/session-1",
        None,
        {"sessionId": "session-1", "ended": True},
        method="DELETE",
    ),
    _ContractCase(
        "agent-feedback",
        lambda _models, agent: agent.submit_feedback(
            "session-1", 5, message_id="message-1"
        ),
        lambda _models, agent: agent.submit_feedback(
            "session-1", 5, message_id="message-1"
        ),
        "/einstein/ai-agent/v1/feedback",
        {"sessionId": "session-1", "rating": 5, "messageId": "message-1"},
        {"success": True, "requestId": "feedback-1"},
    ),
    _ContractCase(
        "models-feedback-negative-ack",
        lambda models, _agent: models.submit_feedback("request-1", 5),
        lambda models, _agent: models.submit_feedback("request-1", 5),
        "/einstein/platform/v1/feedback",
        {"requestId": "request-1", "rating": 5},
        {"success": False, "requestId": "request-1"},
    ),
    _ContractCase(
        "agent-feedback-negative-ack",
        lambda _models, agent: agent.submit_feedback("session-1", 5),
        lambda _models, agent: agent.submit_feedback("session-1", 5),
        "/einstein/ai-agent/v1/feedback",
        {"sessionId": "session-1", "rating": 5},
        {"success": False, "requestId": "feedback-1"},
    ),
]


class TestSalesforceAIParity:
    @pytest.mark.parametrize("case", _CASES, ids=lambda case: case.name)
    async def test_non_streaming_methods_have_equivalent_contracts(
        self, case: _ContractCase
    ) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=case.response)

        with HttpxSyncTransport(
            client=httpx.Client(transport=httpx.MockTransport(handler))
        ) as transport:
            client = _sync_client(transport)
            sync_result = case.sync_call(
                SalesforceModelsService(client), SalesforceAgentService(client)
            )
        async with HttpxAsyncTransport(
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        ) as async_transport:
            async_client = _async_client(async_transport)
            async_result = await case.async_call(
                AsyncSalesforceModelsService(async_client),
                AsyncSalesforceAgentService(async_client),
            )

        assert isinstance(sync_result, BaseModel)
        assert isinstance(async_result, type(sync_result))
        assert sync_result.model_dump() == async_result.model_dump()
        assert (
            sync_result.model_dump(by_alias=True, exclude_unset=True) == case.response
        )
        assert len(requests) == 2
        for request in requests:
            assert request.method == case.method
            assert str(request.url) == DUMMY_INSTANCE_URL + case.path
            assert (
                json.loads(request.content) if request.content else None
            ) == case.payload


_STREAM_LINES = [
    "event: delta",
    'data: {"text":"hello"}',
    "",
    "event: done",
    'data: {"finished":true}',
    "",
]
_STREAM_BODY = "\n".join([*_STREAM_LINES, ""]).encode()


class _SyncAIStream(httpx.SyncByteStream):
    def __init__(self, error: BaseException | None = None) -> None:
        self.error = error
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        yield _STREAM_BODY[:10]
        if self.error is not None:
            raise self.error
        yield _STREAM_BODY[10:]

    def close(self) -> None:
        self.closed = True


class _AsyncAIStream(httpx.AsyncByteStream):
    def __init__(self, error: BaseException | None = None) -> None:
        self.error = error
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield _STREAM_BODY[:10]
        if self.error is not None:
            raise self.error
        yield _STREAM_BODY[10:]

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.parametrize("service", ["models", "agent"])
class TestSalesforceAIStreaming:
    def test_sync_preserves_lines_and_closes_after_consumption(
        self, service: str
    ) -> None:
        raw = _SyncAIStream()
        with HttpxSyncTransport(
            client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda _request: httpx.Response(200, stream=raw)
                )
            )
        ) as transport:
            client = _sync_client(transport)
            response = (
                SalesforceModelsService(client).generate_chat([], stream=True)
                if service == "models"
                else SalesforceAgentService(client).send_message_streaming(
                    "session-1", "hello"
                )
            )
            assert isinstance(response, StreamingResponse)
            assert not raw.closed
            with response:
                assert list(response.iter_lines()) == _STREAM_LINES
        assert raw.closed

    async def test_async_preserves_lines_and_closes_after_consumption(
        self, service: str
    ) -> None:
        raw = _AsyncAIStream()
        async with HttpxAsyncTransport(
            client=httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _request: httpx.Response(200, stream=raw)
                )
            )
        ) as transport:
            client = _async_client(transport)
            response = (
                await AsyncSalesforceModelsService(client).generate_chat(
                    [], stream=True
                )
                if service == "models"
                else await AsyncSalesforceAgentService(client).send_message_streaming(
                    "session-1", "hello"
                )
            )
            assert isinstance(response, AsyncStreamingResponse)
            assert not raw.closed
            async with response:
                assert [line async for line in response.aiter_lines()] == _STREAM_LINES
        assert raw.closed

    def test_sync_interruption_is_typed_without_replaying_request(
        self, service: str
    ) -> None:
        error = httpx.ReadError("stream interrupted")
        raw = _SyncAIStream(error)
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, stream=raw)

        with HttpxSyncTransport(
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            middlewares=[RetryMiddleware(HttpRetryPolicy(backoff_initial=0))],
        ) as transport:
            client = _sync_client(transport)
            response = (
                SalesforceModelsService(client).generate_chat([], stream=True)
                if service == "models"
                else SalesforceAgentService(client).send_message_streaming(
                    "session-1", "hello"
                )
            )
            assert isinstance(response, StreamingResponse)
            with pytest.raises(StreamInterruptedError) as raised:
                with response:
                    chunks = response.iter_bytes()
                    assert next(chunks) == _STREAM_BODY[:10]
                    next(chunks)
        assert raised.value.__cause__ is error
        assert len(requests) == 1
        assert raw.closed

    @pytest.mark.parametrize("cancel", [False, True])
    async def test_async_interruption_or_cancellation_does_not_replay(
        self, service: str, cancel: bool
    ) -> None:
        error = (
            asyncio.CancelledError()
            if cancel
            else httpx.ReadError("stream interrupted")
        )
        raw = _AsyncAIStream(error)
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, stream=raw)

        async with HttpxAsyncTransport(
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            middlewares=[AsyncRetryMiddleware(HttpRetryPolicy(backoff_initial=0))],
        ) as transport:
            client = _async_client(transport)
            response = (
                await AsyncSalesforceModelsService(client).generate_chat(
                    [], stream=True
                )
                if service == "models"
                else await AsyncSalesforceAgentService(client).send_message_streaming(
                    "session-1", "hello"
                )
            )
            assert isinstance(response, AsyncStreamingResponse)
            with pytest.raises(
                asyncio.CancelledError if cancel else StreamInterruptedError
            ) as raised:
                async with response:
                    chunks = response.aiter_bytes()
                    assert await anext(chunks) == _STREAM_BODY[:10]
                    await anext(chunks)
        if cancel:
            assert raised.value is error
        else:
            assert raised.value.__cause__ is error
        assert len(requests) == 1
        assert raw.closed


class TestSalesforceAIFeedback:
    @pytest.mark.parametrize(
        ("service", "field", "message"),
        [
            ("models", "rating", "Rating is invalid"),
            ("models", "requestId", "Unknown request ID"),
            ("agent", "rating", "Rating is invalid"),
            ("agent", "sessionId", "Unknown session ID"),
        ],
    )
    async def test_provider_validation_errors_preserve_details(
        self, service: str, field: str, message: str
    ) -> None:
        payload = [
            {
                "errorCode": "FIELD_CUSTOM_VALIDATION_EXCEPTION",
                "message": message,
                "fields": [field],
            }
        ]

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json=payload)

        with HttpxSyncTransport(
            client=httpx.Client(transport=httpx.MockTransport(handler))
        ) as transport:
            client = _sync_client(transport)
            with pytest.raises(SalesforceValidationError) as sync_error:
                if service == "models":
                    SalesforceModelsService(client).submit_feedback("", 999)
                else:
                    SalesforceAgentService(client).submit_feedback("", 999)
        async with HttpxAsyncTransport(
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        ) as async_transport:
            async_client = _async_client(async_transport)
            with pytest.raises(SalesforceValidationError) as async_error:
                if service == "models":
                    await AsyncSalesforceModelsService(async_client).submit_feedback(
                        "", 999
                    )
                else:
                    await AsyncSalesforceAgentService(async_client).submit_feedback(
                        "", 999
                    )

        assert sync_error.value.status_code == async_error.value.status_code == 400
        assert str(sync_error.value) == str(async_error.value)
        assert sync_error.value.errors[0].message == message
        assert sync_error.value.errors[0].fields == [field]
        assert sync_error.value.errors == async_error.value.errors

    @pytest.mark.parametrize(
        ("model", "identifier"),
        [(ModelsFeedbackRequest, "request_id"), (AgentFeedbackRequest, "session_id")],
    )
    def test_feedback_models_reject_missing_ids(
        self, model: type[BaseModel], identifier: str
    ) -> None:
        with pytest.raises(ValidationError) as raised:
            model.model_validate({"rating": 5})
        assert raised.value.errors()[0]["loc"] == (identifier,)

    @pytest.mark.parametrize(
        ("model", "identifier"),
        [(ModelsFeedbackRequest, "request_id"), (AgentFeedbackRequest, "session_id")],
    )
    def test_feedback_models_reject_invalid_rating_types(
        self, model: type[BaseModel], identifier: str
    ) -> None:
        with pytest.raises(ValidationError) as raised:
            model.model_validate({identifier: "id-1", "rating": "invalid"})
        assert raised.value.errors()[0]["loc"] == ("rating",)
