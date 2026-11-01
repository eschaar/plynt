"""Verify Django request-ID scoping across sync and async request stacks"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Generator, Iterable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

import pytest

django = pytest.importorskip("django")

from django.conf import settings  # noqa: E402
from django.http import (  # noqa: E402
    HttpRequest,
    HttpResponse,
    JsonResponse,
    StreamingHttpResponse,
)
from django.http.response import HttpResponseBase  # noqa: E402
from django.test import Client, RequestFactory, override_settings  # noqa: E402
from django.test.client import AsyncClient  # noqa: E402
from django.urls import path  # noqa: E402
from django.utils.decorators import sync_and_async_middleware  # noqa: E402

from plynt.adapters.django import RequestIDMiddleware  # noqa: E402
from plynt.base import RequestIDPolicy, get_request_id  # noqa: E402

if not settings.configured:
    settings.configure(
        SECRET_KEY="request-id-tests",
        INSTALLED_APPS=[],
        MIDDLEWARE=[],
    )
    django.setup()


def sync_view(request: HttpRequest) -> HttpResponse:
    return JsonResponse({"request_id": get_request_id(), "path": request.path})


async def async_view(request: HttpRequest) -> HttpResponse:
    await asyncio.sleep(0)
    return sync_view(request)


def failing_view(request: HttpRequest) -> HttpResponse:
    raise ValueError("view failure")


urlpatterns = [
    path("sync/", sync_view),
    path("async/", async_view),
    path("failure/", failing_view),
]


def untrusted_request_ids(
    get_response: Callable[
        [HttpRequest], HttpResponseBase | Awaitable[HttpResponseBase]
    ],
) -> RequestIDMiddleware:
    return RequestIDMiddleware(
        get_response,
        policy=RequestIDPolicy(trust_inbound=False, generator=lambda: "generated"),
    )


untrusted_request_ids = sync_and_async_middleware(untrusted_request_ids)


@pytest.fixture
def request_stack() -> Generator[None, None, None]:
    with override_settings(
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=["testserver"],
        DEBUG=False,
        APPEND_SLASH=True,
        MIDDLEWARE=[
            "plynt.adapters.django.RequestIDMiddleware",
            "django.middleware.common.CommonMiddleware",
        ],
    ):
        yield


class TestRequestIDMiddleware:
    def test_streaming_response_is_not_consumed_and_context_is_reset(self) -> None:
        def handler(request: HttpRequest) -> HttpResponseBase:
            return StreamingHttpResponse(iter([b"chunk"]))

        response = RequestIDMiddleware(handler)(
            RequestFactory().get("/", headers={"X-Request-ID": "stream"})
        )
        assert isinstance(response, StreamingHttpResponse)
        assert response["X-Request-ID"] == "stream"
        assert get_request_id() is None
        content = response.streaming_content
        assert isinstance(content, Iterable)
        assert list(content) == [b"chunk"]

    @pytest.mark.parametrize("incoming", [None, "", "bad id", "a" * 129])
    def test_missing_or_invalid_id_is_generated_and_echoed(
        self, incoming: str | None
    ) -> None:
        observed: list[str | None] = []

        def handler(request: HttpRequest) -> HttpResponse:
            observed.append(get_request_id())
            return HttpResponse()

        headers = {} if incoming is None else {"X-Request-ID": incoming}
        response = RequestIDMiddleware(handler)(
            RequestFactory().get("/", headers=headers)
        )
        assert isinstance(response, HttpResponse)
        request_id = response["X-Request-ID"]
        assert UUID(hex=request_id).version == 4
        assert observed == [request_id]
        assert get_request_id() is None

    def test_custom_policy_replaces_untrusted_and_existing_response_id(self) -> None:
        def handler(request: HttpRequest) -> HttpResponse:
            return HttpResponse(headers={"Request-ID": "stale"})

        policy = RequestIDPolicy(
            header_name="Request-ID", trust_inbound=False, generator=lambda: "fresh"
        )
        response = RequestIDMiddleware(handler, policy=policy)(
            RequestFactory().get("/", headers={"Request-ID": "untrusted"})
        )
        assert isinstance(response, HttpResponse)
        assert response["Request-ID"] == "fresh"
        assert get_request_id() is None

    def test_exception_restores_previous_context(self) -> None:
        def failing(request: HttpRequest) -> HttpResponse:
            assert get_request_id() == "inner"
            raise ValueError("handler failure")

        with RequestIDPolicy().scope("outer"):
            with pytest.raises(ValueError, match="handler failure"):
                RequestIDMiddleware(failing)(
                    RequestFactory().get("/", headers={"X-Request-ID": "inner"})
                )
            assert get_request_id() == "outer"
        assert get_request_id() is None

    @pytest.mark.asyncio
    async def test_async_exception_and_cancellation_restore_context(self) -> None:
        async def failing(request: HttpRequest) -> HttpResponse:
            assert get_request_id() == "inner"
            raise asyncio.CancelledError

        middleware = RequestIDMiddleware(failing)
        assert inspect.iscoroutinefunction(middleware)
        with RequestIDPolicy().scope("outer"):
            response = middleware(
                RequestFactory().get("/", headers={"X-Request-ID": "inner"})
            )
            assert inspect.isawaitable(response)
            with pytest.raises(asyncio.CancelledError):
                await response
            assert get_request_id() == "outer"

    def test_concurrent_sync_requests_keep_ids_isolated(self) -> None:
        barrier = Barrier(2)

        def handler(request: HttpRequest) -> HttpResponse:
            barrier.wait(timeout=5)
            return HttpResponse(get_request_id())

        middleware = RequestIDMiddleware(handler)

        def send(request_id: str) -> tuple[bytes, str, str | None]:
            response = middleware(
                RequestFactory().get("/", headers={"X-Request-ID": request_id})
            )
            assert isinstance(response, HttpResponse)
            return response.content, response["X-Request-ID"], get_request_id()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(send, "first")
            second = executor.submit(send, "second")
            assert first.result() == (b"first", "first", None)
            assert second.result() == (b"second", "second", None)

    @pytest.mark.asyncio
    async def test_concurrent_async_requests_keep_ids_isolated(self) -> None:
        async def handler(request: HttpRequest) -> HttpResponse:
            await asyncio.sleep(0)
            return HttpResponse(get_request_id())

        middleware = RequestIDMiddleware(handler)

        async def send(request_id: str) -> tuple[bytes, str, str | None]:
            response = middleware(
                RequestFactory().get("/", headers={"X-Request-ID": request_id})
            )
            assert inspect.isawaitable(response)
            resolved = await response
            assert isinstance(resolved, HttpResponse)
            return resolved.content, resolved["X-Request-ID"], get_request_id()

        first, second = await asyncio.gather(send("first"), send("second"))
        assert first == (b"first", "first", None)
        assert second == (b"second", "second", None)


class TestDjangoRequestIDStack:
    @pytest.mark.asyncio
    async def test_policy_factory_supports_async_stack_and_rejects_inbound_id(
        self, request_stack: object
    ) -> None:
        with override_settings(
            MIDDLEWARE=[
                f"{__name__}.untrusted_request_ids",
                "django.middleware.common.CommonMiddleware",
            ]
        ):
            response = await AsyncClient().get(
                "/async/", headers={"X-Request-ID": "untrusted"}
            )
            assert response["X-Request-ID"] == "generated"
            assert response.json()["request_id"] == "generated"
        assert get_request_id() is None

    @pytest.mark.parametrize("endpoint", ["sync", "async"])
    def test_sync_client_keeps_id_in_views_redirects_and_final_response(
        self, request_stack: object, endpoint: str
    ) -> None:
        client = Client()
        response = client.get(
            f"/{endpoint}", headers={"X-Request-ID": "sync-client"}, follow=True
        )
        assert response.redirect_chain == [(f"/{endpoint}/", 301)]
        assert response["X-Request-ID"] == "sync-client"
        assert response.json() == {"request_id": "sync-client", "path": f"/{endpoint}/"}
        redirect = client.get(f"/{endpoint}", headers={"X-Request-ID": "redirect"})
        assert redirect.status_code == 301
        assert redirect["X-Request-ID"] == "redirect"
        assert get_request_id() is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", ["sync", "async"])
    async def test_async_client_keeps_id_in_views_redirects_and_final_response(
        self, request_stack: object, endpoint: str
    ) -> None:
        client = AsyncClient()
        redirect = await client.get(
            f"/{endpoint}", headers={"X-Request-ID": "async-client"}
        )
        assert redirect.status_code == 301
        assert redirect["X-Request-ID"] == "async-client"
        response = await client.get(
            redirect["Location"], headers={"X-Request-ID": "async-client"}
        )
        assert response["X-Request-ID"] == "async-client"
        assert response.json() == {
            "request_id": "async-client",
            "path": f"/{endpoint}/",
        }
        assert get_request_id() is None

    def test_framework_error_and_early_response_carry_id(
        self, request_stack: object
    ) -> None:
        client = Client(raise_request_exception=False)
        failure = client.get("/failure/", headers={"X-Request-ID": "failed"})
        assert failure.status_code == 500
        assert failure["X-Request-ID"] == "failed"
        missing = client.get("/missing/", headers={"X-Request-ID": "missing"})
        assert missing.status_code == 404
        assert missing["X-Request-ID"] == "missing"
        assert get_request_id() is None
