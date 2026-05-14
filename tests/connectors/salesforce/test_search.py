"""Tests for SalesforceSearchService and AsyncSalesforceSearchService."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from plynth.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynth.connectors.salesforce.models import SalesforceSearchResponse
from plynth.connectors.salesforce.search import (
    AsyncSalesforceSearchService,
    SalesforceSearchService,
)
from plynth.connectors.salesforce.sobject import DEFAULT_API_VERSION
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import JSONRenderer
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
) -> tuple[SalesforceSearchService, MockSyncTransport]:
    """Build a SalesforceSearchService backed by a sync mock transport."""
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
    return SalesforceSearchService(client), transport


def _make_async_service(
    *,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[AsyncSalesforceSearchService, MockAsyncTransport]:
    """Build an AsyncSalesforceSearchService backed by an async mock transport."""
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
    return AsyncSalesforceSearchService(client), transport


_SEARCH_PAYLOAD: dict[str, list[dict[str, Any]]] = {
    "searchRecords": [
        {
            "attributes": {
                "type": "Account",
                "url": "/services/data/v59.0/sobjects/Account/001xxx",
            },
            "Id": "001xxx",
            "Name": "Acme",
        },
        {
            "attributes": {
                "type": "Contact",
                "url": "/services/data/v59.0/sobjects/Contact/003xxx",
            },
            "Id": "003xxx",
            "Name": "Jane Doe",
        },
    ]
}


class TestSalesforceSearchService:
    """Tests for SalesforceSearchService."""

    def test_search_sends_correct_path_and_param(self) -> None:
        """GET /search is called with the SOSL string passed as the ``q`` parameter."""
        svc, transport = _make_service(content=_json_bytes(_SEARCH_PAYLOAD))
        svc.search("FIND {Acme} IN NAME FIELDS RETURNING Account(Id, Name)")
        sent = transport.send.call_args[0][0]
        assert sent.method == "GET"
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/search")
        assert sent.params == {
            "q": "FIND {Acme} IN NAME FIELDS RETURNING Account(Id, Name)"
        }

    def test_search_returns_typed_response(self) -> None:
        """Returns a typed SalesforceSearchResponse with all records populated."""
        svc, _ = _make_service(content=_json_bytes(_SEARCH_PAYLOAD))
        result = svc.search("FIND {Acme}")
        assert isinstance(result, SalesforceSearchResponse)
        assert len(result.search_records) == 2

    def test_search_record_fields(self) -> None:
        """Each search record exposes id, sobject_type, and field access by key."""
        svc, _ = _make_service(content=_json_bytes(_SEARCH_PAYLOAD))
        result = svc.search("FIND {Acme}")
        record = result.search_records[0]
        assert record.id == "001xxx"
        assert record.sobject_type == "Account"
        assert record["Name"] == "Acme"

    def test_search_empty_result(self) -> None:
        """An empty searchRecords payload returns a response with no records."""
        payload: dict[str, list[Any]] = {"searchRecords": []}
        svc, _ = _make_service(content=_json_bytes(payload))
        result = svc.search("FIND {NoMatch}")
        assert result.search_records == []

    def test_quick_search_wraps_find_syntax(self) -> None:
        """quick_search wraps the keyword in FIND {…} and sends it as the SOSL query."""
        payload: dict[str, list[Any]] = {"searchRecords": []}
        svc, transport = _make_service(content=_json_bytes(payload))
        svc.quick_search("Acme")
        sent = transport.send.call_args[0][0]
        assert sent.params == {"q": "FIND {Acme}"}

    def test_custom_api_version(self) -> None:
        """Passing api_version at construction routes requests to the correct path."""
        transport = MockSyncTransport(content=_json_bytes({"searchRecords": []}))
        client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        svc = SalesforceSearchService(client, api_version="62.0")
        svc.search("FIND {x}")
        sent = transport.send.call_args[0][0]
        assert "/v62.0/" in sent.url

    def test_facade_search_returns_service(self) -> None:
        """Calling search() on the sync facade returns a SalesforceSearchService."""
        transport = MockSyncTransport(content=b"{}")
        client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        facade = SalesforceAPIFacade(client)
        svc = facade.search()
        assert isinstance(svc, SalesforceSearchService)


class TestAsyncSalesforceSearchService:
    """Tests for AsyncSalesforceSearchService."""

    async def test_search_sends_correct_path_and_param(self) -> None:
        """GET /search is called with the SOSL string passed as the ``q`` parameter."""
        svc, transport = _make_async_service(content=_json_bytes(_SEARCH_PAYLOAD))
        await svc.search("FIND {Acme} IN NAME FIELDS RETURNING Account(Id, Name)")
        sent = transport.send.call_args[0][0]
        assert sent.method == "GET"
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/search")
        assert sent.params == {
            "q": "FIND {Acme} IN NAME FIELDS RETURNING Account(Id, Name)"
        }

    async def test_search_returns_typed_response(self) -> None:
        """Returns a typed SalesforceSearchResponse with all records populated."""
        svc, _ = _make_async_service(content=_json_bytes(_SEARCH_PAYLOAD))
        result = await svc.search("FIND {Acme}")
        assert isinstance(result, SalesforceSearchResponse)
        assert len(result.search_records) == 2

    async def test_search_record_fields(self) -> None:
        """Each search record exposes id, sobject_type, and field access by key."""
        svc, _ = _make_async_service(content=_json_bytes(_SEARCH_PAYLOAD))
        result = await svc.search("FIND {Acme}")
        record = result.search_records[1]
        assert record.id == "003xxx"
        assert record.sobject_type == "Contact"
        assert record["Name"] == "Jane Doe"

    async def test_quick_search_wraps_find_syntax(self) -> None:
        """quick_search wraps the keyword in FIND {…} and sends it as the SOSL query."""
        payload: dict[str, list[Any]] = {"searchRecords": []}
        svc, transport = _make_async_service(content=_json_bytes(payload))
        await svc.quick_search("Acme")
        sent = transport.send.call_args[0][0]
        assert sent.params == {"q": "FIND {Acme}"}

    async def test_facade_search_returns_service(self) -> None:
        """The async facade search() returns an AsyncSalesforceSearchService."""
        transport = MockAsyncTransport(content=b"{}")
        client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        facade = AsyncSalesforceAPIFacade(client)
        svc = facade.search()
        assert isinstance(svc, AsyncSalesforceSearchService)

    async def test_custom_api_version(self) -> None:
        """Passing api_version at construction routes async requests correctly."""
        transport = MockAsyncTransport(content=_json_bytes({"searchRecords": []}))
        client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        svc = AsyncSalesforceSearchService(client, api_version="62.0")

        await svc.search("FIND {x}")

        sent = transport.send.call_args[0][0]
        assert "/v62.0/" in sent.url

    @pytest.mark.parametrize(
        "sosl,exp_q",
        [
            ("FIND {test}", "FIND {test}"),
            ("FIND {a b} IN ALL FIELDS", "FIND {a b} IN ALL FIELDS"),
        ],
    )
    async def test_search_passes_sosl_verbatim(self, sosl: str, exp_q: str) -> None:
        """The SOSL string is forwarded verbatim as the ``q`` query parameter."""
        svc, transport = _make_async_service(content=_json_bytes({"searchRecords": []}))
        await svc.search(sosl)
        sent = transport.send.call_args[0][0]
        assert sent.params == {"q": exp_q}

    async def test_parallel_search_resolves_api_version_once(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Parallel search calls resolve API version only once per service."""
        svc, _ = _make_async_service(content=_json_bytes(_SEARCH_PAYLOAD))
        call_count = 0

        async def fake_resolve(
            _client: AsyncAPIClient,
            _api_version: str | None,
        ) -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0)
            return "63.0"

        monkeypatch.setattr(
            "plynth.connectors.salesforce.search.resolve_async_api_version",
            fake_resolve,
        )

        await asyncio.gather(
            svc.search("FIND {Acme}"),
            svc.search("FIND {Jane}"),
        )

        assert call_count == 1
