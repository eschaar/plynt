"""Execute the documented Salesforce lifespan with mocked HTTP boundaries"""

import asyncio
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest

pytest.importorskip("fastapi")

from fastapi import Request

from plynt.connectors.salesforce.client import AsyncSalesforceAPIClient

_GUIDE = (
    Path(__file__).resolve().parents[3]
    / "docs/connectors/salesforce/user/how-to/use-fastapi-lifespan.md"
)


@pytest.fixture
def recipe(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], list[httpx.Request], list[httpx.AsyncClient]]:
    calls: list[httpx.Request] = []
    clients: list[httpx.AsyncClient] = []
    original = httpx.AsyncClient

    async def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        await asyncio.sleep(0)
        if request.url.path == "/services/oauth2/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "test-token",
                    "instance_url": "https://org.example.invalid",
                    "expires_in": 3600,
                },
            )
        return httpx.Response(200, json={"ok": True})

    def create_client(**kwargs: Any) -> httpx.AsyncClient:
        client = original(transport=httpx.MockTransport(respond), **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(httpx, "AsyncClient", create_client)
    monkeypatch.setenv("SF_CLIENT_ID", "test-client")
    monkeypatch.setenv("SF_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv(
        "SF_TOKEN_URL", "https://login.example.invalid/services/oauth2/token"
    )
    source = _GUIDE.read_text().split("```python\n", 1)[1].split("```", 1)[0]
    namespace: dict[str, Any] = {}
    # Execute only the fixed, repository-owned example, never external input.
    exec(compile(source, str(_GUIDE), "exec"), namespace)  # noqa: S102
    return namespace, calls, clients


class TestSalesforceFastAPILifespanRecipe:
    @pytest.mark.asyncio
    async def test_concurrent_calls_share_auth_and_repeated_lifespans_close_resources(
        self,
        recipe: tuple[dict[str, Any], list[httpx.Request], list[httpx.AsyncClient]],
    ) -> None:
        namespace, calls, clients = recipe
        app = namespace["app"]
        request = Request({"type": "http", "app": app})
        previous: AsyncSalesforceAPIClient | None = None
        for _ in range(2):
            async with namespace["lifespan"](app):
                client = namespace["get_salesforce_client"](request)
                assert isinstance(client, AsyncSalesforceAPIClient)
                assert client is namespace["get_salesforce_client"](request)
                assert client is not previous
                responses = await asyncio.gather(
                    client.get("/items"), client.get("/items")
                )
                assert all(response.status_code == 200 for response in responses)
                previous = client
            assert not hasattr(app.state, "salesforce")
            assert all(client.is_closed for client in clients)
        tokens = [call for call in calls if call.url.path == "/services/oauth2/token"]
        api_calls = [call for call in calls if call.url.path == "/items"]
        assert len(tokens) == 2
        assert len(api_calls) == 4
        assert all(call.url.host == "org.example.invalid" for call in api_calls)
        assert all(
            call.headers["Authorization"] == "Bearer test-token" for call in api_calls
        )
        with pytest.raises(RuntimeError, match="outside app lifespan"):
            namespace["get_salesforce_client"](request)

    @pytest.mark.asyncio
    async def test_startup_client_construction_failure_closes_both_transports(
        self,
        recipe: tuple[dict[str, Any], list[httpx.Request], list[httpx.AsyncClient]],
    ) -> None:
        namespace, calls, clients = recipe

        def failing(**kwargs: object) -> AsyncSalesforceAPIClient:
            raise ValueError("startup failure")

        namespace["AsyncSalesforceAPIClient"] = failing
        with pytest.raises(ValueError, match="startup failure"):
            async with namespace["lifespan"](namespace["app"]):
                pytest.fail("Startup must fail before yielding")
        assert len(clients) == 2
        assert all(client.is_closed for client in clients)
        assert calls == []
        assert not hasattr(namespace["app"].state, "salesforce")

    @pytest.mark.asyncio
    async def test_handler_failure_closes_resources_and_removes_client(
        self,
        recipe: tuple[dict[str, Any], list[httpx.Request], list[httpx.AsyncClient]],
    ) -> None:
        namespace, calls, clients = recipe
        with pytest.raises(ValueError, match="handler failure"):
            async with namespace["lifespan"](namespace["app"]):
                raise ValueError("handler failure")
        assert len(clients) == 2
        assert all(client.is_closed for client in clients)
        assert calls == []
        assert not hasattr(namespace["app"].state, "salesforce")

    @pytest.mark.asyncio
    async def test_missing_configuration_fails_before_allocating_resources(
        self,
        recipe: tuple[dict[str, Any], list[httpx.Request], list[httpx.AsyncClient]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        namespace, calls, clients = recipe
        monkeypatch.delenv("SF_CLIENT_SECRET")
        with pytest.raises(KeyError, match="SF_CLIENT_SECRET"):
            async with namespace["lifespan"](namespace["app"]):
                pytest.fail("Startup must reject missing credentials")
        assert clients == []
        assert calls == []
