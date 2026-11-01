"""Verify pure ASGI request-ID lifecycle and FastAPI integration"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from plynt.adapters.fastapi import RequestIDMiddleware
from plynt.base import RequestIDPolicy, get_request_id


async def _receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


class TestASGIRequestIDMiddleware:
    @pytest.mark.asyncio
    async def test_send_failure_restores_context_without_swallowing_error(self) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            await send({"type": "http.response.start", "status": 200})

        async def send(message: Message) -> None:
            assert get_request_id() == "inner"
            raise ConnectionError("disconnected")

        with RequestIDPolicy().scope("outer"):
            with pytest.raises(ConnectionError, match="disconnected"):
                await RequestIDMiddleware(app)(
                    {"type": "http", "headers": [(b"x-request-id", b"inner")]},
                    _receive,
                    send,
                )
            assert get_request_id() == "outer"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "headers",
        [
            [],
            [(b"x-request-id", b"bad id")],
            [(b"x-request-id", b"\xff")],
            [(b"x-request-id", b"a" * 129)],
            [(b"x-request-id", b"first"), (b"X-Request-ID", b"second")],
        ],
    )
    async def test_missing_invalid_or_duplicate_ids_are_replaced(
        self, headers: list[tuple[bytes, bytes]]
    ) -> None:
        sent: list[Message] = []

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            assert get_request_id() == "generated"
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"ok"})

        async def send(message: Message) -> None:
            sent.append(message)

        await RequestIDMiddleware(
            app, policy=RequestIDPolicy(generator=lambda: "generated")
        )({"type": "http", "headers": headers}, _receive, send)
        assert sent[0]["headers"] == [(b"x-request-id", b"generated")]
        assert sent[1] == {"type": "http.response.body", "body": b"ok"}
        assert get_request_id() is None

    @pytest.mark.asyncio
    async def test_custom_header_replaces_response_duplicates_without_mutating_message(
        self,
    ) -> None:
        original: Message = {
            "type": "http.response.start",
            "status": 302,
            "headers": [
                (b"location", b"/final"),
                (b"Request-ID", b"stale"),
                (b"request-id", b"other"),
            ],
        }
        sent: list[Message] = []

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            assert get_request_id() == "trusted"
            await send(original)

        async def send(message: Message) -> None:
            sent.append(message)

        await RequestIDMiddleware(
            app, policy=RequestIDPolicy(header_name="Request-ID")
        )(
            {"type": "http", "headers": [(b"REQUEST-ID", b"trusted")]},
            _receive,
            send,
        )
        assert sent[0]["headers"] == [
            (b"location", b"/final"),
            (b"request-id", b"trusted"),
        ]
        assert len(original["headers"]) == 3

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scope_type", ["lifespan", "websocket"])
    async def test_non_http_scopes_pass_through_unchanged(
        self, scope_type: str
    ) -> None:
        scope: Scope = {"type": scope_type}
        observed: list[str | None] = []

        async def send(message: Message) -> None:
            pass

        async def app(received: Scope, receive: Receive, sender: Send) -> None:
            assert received is scope
            assert receive is _receive
            assert sender is send
            observed.append(get_request_id())

        with RequestIDPolicy().scope("outer"):
            await RequestIDMiddleware(app)(scope, _receive, send)
            assert observed == ["outer"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("failure", [ValueError, asyncio.CancelledError])
    async def test_failure_restores_previous_context(
        self, failure: type[BaseException]
    ) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            assert get_request_id() == "inner"
            raise failure()

        async def send(message: Message) -> None:
            pass

        with RequestIDPolicy().scope("outer"):
            with pytest.raises(failure):
                await RequestIDMiddleware(app)(
                    {"type": "http", "headers": [(b"x-request-id", b"inner")]},
                    _receive,
                    send,
                )
            assert get_request_id() == "outer"

    @pytest.mark.asyncio
    async def test_concurrent_requests_and_stream_chunks_keep_context(self) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            await asyncio.sleep(0)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await asyncio.sleep(0)
            await send(
                {
                    "type": "http.response.body",
                    "body": str(get_request_id()).encode(),
                    "more_body": True,
                }
            )
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        middleware = RequestIDMiddleware(app)

        async def request(request_id: str) -> list[Message]:
            messages: list[Message] = []

            async def send(message: Message) -> None:
                messages.append(message)

            await middleware(
                {"type": "http", "headers": [(b"x-request-id", request_id.encode())]},
                _receive,
                send,
            )
            assert get_request_id() is None
            return messages

        first, second = await asyncio.gather(request("first"), request("second"))
        assert first[0]["headers"] == [(b"x-request-id", b"first")]
        assert second[0]["headers"] == [(b"x-request-id", b"second")]
        assert first[1]["body"] == b"first"
        assert second[1]["body"] == b"second"


class TestFastAPIRequestIDMiddleware:
    @pytest.mark.parametrize("async_endpoint", [False, True])
    def test_redirect_and_sync_async_endpoint_share_trusted_id(
        self, async_endpoint: bool
    ) -> None:
        app = FastAPI()

        def sync_endpoint() -> dict[str, str | None]:
            return {"request_id": get_request_id()}

        async def async_handler() -> dict[str, str | None]:
            return sync_endpoint()

        app.get("/items/")(async_handler if async_endpoint else sync_endpoint)
        with TestClient(RequestIDMiddleware(app)) as client:
            redirect = client.get(
                "/items", headers={"X-Request-ID": "inbound"}, follow_redirects=False
            )
            assert redirect.status_code == 307
            assert redirect.headers["X-Request-ID"] == "inbound"
            response = client.get(
                redirect.headers["Location"], headers={"X-Request-ID": "inbound"}
            )
            assert response.json() == {"request_id": "inbound"}
            assert response.headers["X-Request-ID"] == "inbound"

    def test_outer_error_response_gets_generated_id(self) -> None:
        app = FastAPI()

        def failing() -> None:
            raise ValueError("failure")

        app.get("/fail")(failing)
        wrapped = RequestIDMiddleware(
            app,
            policy=RequestIDPolicy(trust_inbound=False, generator=lambda: "fresh"),
        )
        with TestClient(wrapped, raise_server_exceptions=False) as client:
            response = client.get("/fail", headers={"X-Request-ID": "untrusted"})
            assert response.status_code == 500
            assert response.headers["X-Request-ID"] == "fresh"
        assert get_request_id() is None
