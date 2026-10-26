"""Tests for plynt.http.policies.HttpRetryPolicy."""

from __future__ import annotations

from http import HTTPStatus
from unittest.mock import AsyncMock, Mock

import httpx2 as httpx
import pytest

from plynt.base.policies import RetryPolicy
from plynt.base.request import Request
from plynt.base.response import AsyncStreamingResponse, StreamingResponse
from plynt.http.policies import HttpRetryPolicy
from plynt.http.transport import HttpxAsyncTransport, HttpxSyncTransport
from plynt.middleware.retry import AsyncRetryMiddleware, RetryMiddleware


class TestHttpRetryPolicy:
    """Test suite for HttpRetryPolicy."""

    def test_default_values(self) -> None:
        """Validate default values."""
        policy = HttpRetryPolicy()
        assert policy.max_attempts == 3
        assert policy.backoff_initial == 0.5
        assert policy.backoff_multiplier == 2.0
        assert policy.backoff_max == 30.0
        assert policy.retry_on_network_error is True
        assert policy.retryable_status_codes == frozenset(
            {
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                HTTPStatus.BAD_GATEWAY,
                HTTPStatus.SERVICE_UNAVAILABLE,
                HTTPStatus.GATEWAY_TIMEOUT,
            }
        )

    def test_inherits_from_retry_policy(self) -> None:
        """Validate inherits from retry policy."""
        assert issubclass(HttpRetryPolicy, RetryPolicy)

    def test_custom_retryable_status_codes_replaces_defaults(self) -> None:
        """Providing retryable_status_codes replaces the defaults entirely."""
        policy = HttpRetryPolicy(
            retryable_status_codes=frozenset(
                {
                    HTTPStatus.TOO_MANY_REQUESTS,
                    HTTPStatus.SERVICE_UNAVAILABLE,
                }
            )
        )
        assert policy.retryable_status_codes == frozenset(
            {
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.SERVICE_UNAVAILABLE,
            }
        )
        # Default codes not included in the override must be absent.
        assert HTTPStatus.INTERNAL_SERVER_ERROR not in policy.retryable_status_codes
        assert HTTPStatus.BAD_GATEWAY not in policy.retryable_status_codes
        assert HTTPStatus.GATEWAY_TIMEOUT not in policy.retryable_status_codes

    def test_custom_max_attempts(self) -> None:
        """Validate custom max attempts."""
        policy = HttpRetryPolicy(max_attempts=5)
        assert policy.max_attempts == 5

    def test_status_codes_are_frozenset(self) -> None:
        """Validate status codes are frozenset."""
        policy = HttpRetryPolicy()
        assert isinstance(policy.retryable_status_codes, frozenset)

    def test_status_codes_accept_raw_integers(self) -> None:
        """Raw integers are valid alongside HTTPStatus values (IntEnum is int)."""
        policy = HttpRetryPolicy(retryable_status_codes=frozenset({429, 503}))
        assert 429 in policy.retryable_status_codes
        assert HTTPStatus.SERVICE_UNAVAILABLE in policy.retryable_status_codes

    @pytest.mark.parametrize(
        "error",
        [
            httpx.ConnectError("connection failed"),
            httpx.ReadError("connection reset"),
            httpx.WriteError("connection reset"),
            httpx.ConnectTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
            httpx.WriteTimeout("timed out"),
            httpx.PoolTimeout("timed out"),
            httpx.RemoteProtocolError("server disconnected"),
            httpx.ProxyError("proxy connection failed"),
            ConnectionError("connection failed"),
            TimeoutError("timed out"),
            OSError("network failed"),
        ],
    )
    def test_default_classifier_accepts_network_errors(
        self, error: BaseException
    ) -> None:
        assert HttpRetryPolicy().retryable_exception_classifier(error)

    @pytest.mark.parametrize(
        "error",
        [
            httpx.LocalProtocolError("invalid request"),
            httpx.UnsupportedProtocol("unsupported URL"),
            httpx.HTTPStatusError(
                "bad request",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(400),
            ),
            ValueError("invalid input"),
            TypeError("invalid type"),
        ],
    )
    def test_default_classifier_rejects_non_network_errors(
        self, error: BaseException
    ) -> None:
        assert not HttpRetryPolicy().retryable_exception_classifier(error)

    def test_explicit_classifier_replaces_http_default(self) -> None:
        policy = HttpRetryPolicy(
            retryable_exception_classifier=lambda exc: isinstance(exc, ValueError)
        )
        assert policy.retryable_exception_classifier(ValueError())
        assert not policy.retryable_exception_classifier(httpx.ConnectError("failed"))


class TestHttpRetryRecovery:
    def test_sync_returns_response_after_backend_failure(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if len(requests) == 1:
                raise httpx.ConnectError("connection failed")
            return httpx.Response(200, content=b"recovered")

        with HttpxSyncTransport(
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            middlewares=[
                RetryMiddleware(HttpRetryPolicy(max_attempts=3, backoff_initial=0))
            ],
        ) as transport:
            result = transport.send(Request("GET", "https://example.com"))

        assert result.content == b"recovered"
        assert len(requests) == 2

    @pytest.mark.asyncio
    async def test_async_returns_response_after_backend_failure(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if len(requests) == 1:
                raise httpx.ConnectError("connection failed")
            return httpx.Response(200, content=b"recovered")

        async with HttpxAsyncTransport(
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            middlewares=[
                AsyncRetryMiddleware(HttpRetryPolicy(max_attempts=3, backoff_initial=0))
            ],
        ) as transport:
            result = await transport.send(Request("GET", "https://example.com"))

        assert result.content == b"recovered"
        assert len(requests) == 2


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ReadTimeout])
@pytest.mark.parametrize(
    ("policy", "expected_attempts"),
    [
        (HttpRetryPolicy(max_attempts=3, backoff_initial=0), 3),
        (
            HttpRetryPolicy(
                max_attempts=3, backoff_initial=0, retry_on_network_error=False
            ),
            1,
        ),
        (
            HttpRetryPolicy(
                max_attempts=3,
                backoff_initial=0,
                retryable_exception_classifier=lambda _exc: False,
            ),
            1,
        ),
    ],
)
class TestHttpNetworkRetries:
    def test_sync_preserves_exception_and_attempt_limit(
        self,
        stream: bool,
        error_type: type[httpx.TransportError],
        policy: HttpRetryPolicy,
        expected_attempts: int,
    ) -> None:
        requests: list[httpx.Request] = []
        error = error_type("network failed")

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            raise error

        with HttpxSyncTransport(
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            middlewares=[RetryMiddleware(policy)],
        ) as transport:
            with pytest.raises(error_type) as raised:
                transport.send(Request("GET", "https://example.com", stream=stream))

        assert raised.value is error
        assert len(requests) == expected_attempts

    @pytest.mark.asyncio
    async def test_async_preserves_exception_and_attempt_limit(
        self,
        stream: bool,
        error_type: type[httpx.TransportError],
        policy: HttpRetryPolicy,
        expected_attempts: int,
    ) -> None:
        requests: list[httpx.Request] = []
        error = error_type("network failed")

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            raise error

        async with HttpxAsyncTransport(
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            middlewares=[AsyncRetryMiddleware(policy)],
        ) as transport:
            with pytest.raises(error_type) as raised:
                await transport.send(
                    Request("GET", "https://example.com", stream=stream)
                )

        assert raised.value is error
        assert len(requests) == expected_attempts


@pytest.mark.parametrize("statuses", [(503, 200), (503, 503, 503), (400,), (503, 400)])
class TestHttpStreamingRetries:
    def test_sync_closes_discarded_streams_before_waiting(
        self, statuses: tuple[int, ...], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        responses: list[httpx.Response] = []
        pending = iter(statuses)

        def assert_closed(_delay: float) -> None:
            assert all(response.is_closed for response in responses)

        def handler(_request: httpx.Request) -> httpx.Response:
            assert_closed(0)
            response = httpx.Response(next(pending), stream=httpx.ByteStream(b"body"))
            responses.append(response)
            return response

        monkeypatch.setattr("plynt.middleware.retry.time.sleep", assert_closed)
        with HttpxSyncTransport(
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            middlewares=[
                RetryMiddleware(HttpRetryPolicy(max_attempts=3, backoff_initial=0))
            ],
        ) as transport:
            try:
                response = transport.send(
                    Request("GET", "https://example.com", stream=True)
                )
                assert isinstance(response, StreamingResponse)
                assert response.status_code == statuses[-1]
                assert [raw.is_closed for raw in responses] == [
                    *([True] * (len(statuses) - 1)),
                    False,
                ]
                response.close()
                assert all(raw.is_closed for raw in responses)
            finally:
                for raw in responses:
                    raw.close()

    @pytest.mark.asyncio
    async def test_async_closes_discarded_streams_before_waiting(
        self, statuses: tuple[int, ...], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        responses: list[httpx.Response] = []
        pending = iter(statuses)

        async def assert_closed(_delay: float) -> None:
            assert all(response.is_closed for response in responses)

        def handler(_request: httpx.Request) -> httpx.Response:
            assert all(response.is_closed for response in responses)
            response = httpx.Response(next(pending), stream=httpx.ByteStream(b"body"))
            responses.append(response)
            return response

        monkeypatch.setattr("plynt.middleware.retry.asyncio.sleep", assert_closed)
        async with HttpxAsyncTransport(
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            middlewares=[
                AsyncRetryMiddleware(HttpRetryPolicy(max_attempts=3, backoff_initial=0))
            ],
        ) as transport:
            try:
                response = await transport.send(
                    Request("GET", "https://example.com", stream=True)
                )
                assert isinstance(response, AsyncStreamingResponse)
                assert response.status_code == statuses[-1]
                assert [raw.is_closed for raw in responses] == [
                    *([True] * (len(statuses) - 1)),
                    False,
                ]
                await response.aclose()
                assert all(raw.is_closed for raw in responses)
            finally:
                for raw in responses:
                    await raw.aclose()


class TestStreamingRetryCleanupFailure:
    def test_sync_cleanup_failure_prevents_next_attempt(self) -> None:
        error = RuntimeError("stream cleanup failed")
        raw = Mock()
        raw.close.side_effect = error
        handler = Mock(return_value=StreamingResponse(503, _raw=raw))

        with pytest.raises(RuntimeError) as raised:
            RetryMiddleware(HttpRetryPolicy(backoff_initial=0)).handle(
                Request("GET", "https://example.com", stream=True), handler
            )

        assert raised.value is error
        assert handler.call_count == 1

    @pytest.mark.asyncio
    async def test_async_cleanup_failure_prevents_next_attempt(self) -> None:
        error = RuntimeError("stream cleanup failed")
        raw = Mock()
        raw.aclose = AsyncMock(side_effect=error)
        handler = AsyncMock(return_value=AsyncStreamingResponse(503, _raw=raw))

        with pytest.raises(RuntimeError) as raised:
            await AsyncRetryMiddleware(HttpRetryPolicy(backoff_initial=0)).handle(
                Request("GET", "https://example.com", stream=True), handler
            )

        assert raised.value is error
        assert handler.await_count == 1
