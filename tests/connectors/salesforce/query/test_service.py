"""Tests for SalesforceQueryService and AsyncSalesforceQueryService."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from plynth.connectors.salesforce.constants import DEFAULT_API_VERSION
from plynth.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynth.connectors.salesforce.models import SalesforceQueryResponse
from plynth.connectors.salesforce.query import (
    AsyncSalesforceObjectQueryService,
    AsyncSalesforceQueryService,
    SalesforceObjectQueryService,
    SalesforceQueryService,
)
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import JSONRenderer
from tests.conftest import MockAsyncTransport, MockSyncTransport

BASE_URL = "https://myorg.my.salesforce.com"
_JSON_RENDERER = JSONRenderer()


def _json_bytes(data: Any) -> bytes:
    """Render arbitrary data to JSON bytes using the shared JSON renderer."""
    return _JSON_RENDERER.render(data)


def _single_page(records: list[dict[str, Any]], *, total: int | None = None) -> bytes:
    """Build a single-page SOQL response payload with done=True."""
    return _json_bytes(
        {
            "totalSize": total if total is not None else len(records),
            "done": True,
            "records": records,
        }
    )


def _page_with_next(
    records: list[dict[str, Any]],
    next_url: str,
    *,
    total: int,
) -> bytes:
    """Build a paginated SOQL response payload with done=False and a next-URL."""
    return _json_bytes(
        {
            "totalSize": total,
            "done": False,
            "nextRecordsUrl": next_url,
            "records": records,
        }
    )


def _make_service(
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[SalesforceQueryService, MockSyncTransport]:
    """Build a SalesforceQueryService backed by a sync mock transport."""
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = APIClient(base_url=BASE_URL, transport=transport)
    return SalesforceQueryService(client), transport


def _make_async_service(
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[AsyncSalesforceQueryService, MockAsyncTransport]:
    """Build an AsyncSalesforceQueryService backed by an async mock transport."""
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
    return AsyncSalesforceQueryService(client), transport


class TestSalesforceQueryService:
    """Test suite for SalesforceQueryService."""

    def test_query_path_and_params(self) -> None:
        """Validate query path and params."""
        content = _single_page([{"Id": "001AAA", "Name": "ACME"}])
        svc, transport = _make_service(content=content)
        result = svc.query("SELECT Id, Name FROM Account LIMIT 1")
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/query")
        assert sent.params == {"q": "SELECT Id, Name FROM Account LIMIT 1"}
        assert isinstance(result, SalesforceQueryResponse)
        assert result.total_size == 1
        assert result.done is True
        assert result.records[0]["Name"] == "ACME"

    def test_query_uses_query_all_when_include_deleted(self) -> None:
        """Validate queryAll endpoint is used when include_deleted is set."""
        content = _single_page([{"Id": "001AAA", "IsDeleted": True}])
        svc, transport = _make_service(content=content)

        result = svc.query(
            "SELECT Id, IsDeleted FROM Account",
            include_deleted=True,
        )

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/queryAll")
        assert sent.params == {"q": "SELECT Id, IsDeleted FROM Account"}
        assert result.records[0]["IsDeleted"] is True

    def test_query_more_uses_next_records_url(self) -> None:
        """Validate query more uses next records url."""
        content = _single_page([{"Id": "001BBB", "Name": "Globex"}])
        next_url = f"/services/data/v{DEFAULT_API_VERSION}/query/01g...XXXX-2000"
        svc, transport = _make_service(content=content)
        result = svc.query_more(next_url)
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(next_url)
        assert isinstance(result, SalesforceQueryResponse)
        assert result.records[0]["Name"] == "Globex"

    def test_query_more_follows_query_all_next_records_url(self) -> None:
        """Validate query_more follows the server-provided queryAll URL."""
        content = _single_page([{"Id": "001BBB", "Name": "Globex"}])
        next_url = f"/services/data/v{DEFAULT_API_VERSION}/queryAll/01g...XXXX-2000"
        svc, transport = _make_service(content=content)

        result = svc.query_more(next_url)

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(next_url)
        assert isinstance(result, SalesforceQueryResponse)
        assert result.records[0]["Name"] == "Globex"

    def test_query_more_from_id_builds_query_path(self) -> None:
        """Validate query_more_from_id builds the query cursor URL."""
        content = _single_page([{"Id": "001BBB", "Name": "Globex"}])
        svc, transport = _make_service(content=content)

        result = svc.query_more_from_id("01g...XXXX-2000")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(
            f"/services/data/v{DEFAULT_API_VERSION}/query/01g...XXXX-2000"
        )
        assert result.records[0]["Name"] == "Globex"

    def test_query_more_from_id_builds_query_all_path_when_requested(self) -> None:
        """Validate query_more_from_id supports queryAll continuation."""
        content = _single_page([{"Id": "001BBB", "Name": "Globex"}])
        svc, transport = _make_service(content=content)

        _ = svc.query_more_from_id("01g...XXXX-2000", include_deleted=True)

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(
            f"/services/data/v{DEFAULT_API_VERSION}/queryAll/01g...XXXX-2000"
        )

    def test_query_more_from_id_rejects_full_path(self) -> None:
        """Validate query_more_from_id rejects full URL fragments."""
        svc, _ = _make_service(content=_single_page([]))

        with pytest.raises(ValueError, match="cursor token"):
            svc.query_more_from_id("/services/data/v59.0/query/01g")

    def test_query_all_iter_single_page(self) -> None:
        """Validate query all iter single page."""
        records = [{"Id": "001AAA"}, {"Id": "001BBB"}]
        content = _single_page(records)
        svc, _ = _make_service(content=content)
        pages = list(svc.query_all_iter("SELECT Id FROM Account"))
        assert len(pages) == 1
        assert pages[0].records == records

    def test_query_all_iter_paginates(self) -> None:
        """Validate query all iter paginates."""
        next_url = f"/services/data/v{DEFAULT_API_VERSION}/query/01g...XXXX-2000"
        page1 = _page_with_next([{"Id": "001AAA"}], next_url, total=2)
        page2 = _single_page([{"Id": "001BBB"}], total=2)

        transport = MockSyncTransport(status_code=200, content=page1)
        client = APIClient(base_url=BASE_URL, transport=transport)
        svc = SalesforceQueryService(client)

        call_count = 0

        def side_effect(_req: Any) -> Any:
            """Return side effect."""
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.content = page1 if call_count == 1 else page2
            return mock_resp

        transport.send.side_effect = side_effect

        pages = list(svc.query_all_iter("SELECT Id FROM Account"))
        assert len(pages) == 2
        assert pages[0].records == [{"Id": "001AAA"}]
        assert pages[1].records == [{"Id": "001BBB"}]

    def test_query_all_returns_flat_list(self) -> None:
        """Validate query all returns flat list."""
        next_url = f"/services/data/v{DEFAULT_API_VERSION}/query/01g...XXXX-2000"
        page1 = _page_with_next([{"Id": "001AAA"}], next_url, total=2)
        page2 = _single_page([{"Id": "001BBB"}], total=2)

        transport = MockSyncTransport(status_code=200, content=page1)
        client = APIClient(base_url=BASE_URL, transport=transport)
        svc = SalesforceQueryService(client)

        call_count = 0

        def side_effect(_req: Any) -> Any:
            """Return side effect."""
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.content = page1 if call_count == 1 else page2
            return mock_resp

        transport.send.side_effect = side_effect

        records = svc.query_all("SELECT Id FROM Account")
        assert records == [{"Id": "001AAA"}, {"Id": "001BBB"}]

    def test_query_all_iter_uses_query_all_when_include_deleted(self) -> None:
        """Validate query_all_iter starts from queryAll when requested."""
        content = _single_page([{"Id": "001AAA", "IsDeleted": True}])
        svc, transport = _make_service(content=content)

        pages = list(
            svc.query_all_iter(
                "SELECT Id, IsDeleted FROM Account",
                include_deleted=True,
            )
        )

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/queryAll")
        assert len(pages) == 1
        assert pages[0].records[0]["IsDeleted"] is True

    def test_query_all_uses_query_all_when_include_deleted(self) -> None:
        """Validate query_all starts from queryAll when requested."""
        content = _single_page([{"Id": "001AAA", "IsDeleted": True}])
        svc, transport = _make_service(content=content)

        records = svc.query_all(
            "SELECT Id, IsDeleted FROM Account",
            include_deleted=True,
        )

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/queryAll")
        assert records == [{"Id": "001AAA", "IsDeleted": True}]

    def test_facade_query_returns_service(self) -> None:
        """Validate facade query returns service."""
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=BASE_URL, transport=transport)
        facade = SalesforceAPIFacade(client)
        svc = facade.query()
        assert isinstance(svc, SalesforceQueryService)

    def test_custom_api_version(self) -> None:
        """Validate custom api version."""
        content = _single_page([])
        transport = MockSyncTransport(status_code=200, content=content)
        client = APIClient(base_url=BASE_URL, transport=transport)
        svc = SalesforceQueryService(client, api_version="62.0")
        svc.query("SELECT Id FROM Account")
        sent = transport.send.call_args[0][0]
        assert "/v62.0/" in sent.url

    @pytest.mark.parametrize(
        "soql,expected_done",
        [
            ("SELECT Id FROM Account LIMIT 1", True),
            ("SELECT Id FROM Lead LIMIT 0", True),
        ],
    )
    def test_query_done_flag(self, soql: str, expected_done: bool) -> None:
        """Validate query done flag."""
        content = _single_page([])
        svc, _ = _make_service(content=content)
        result = svc.query(soql)
        assert result.done is expected_done


class TestAsyncSalesforceQueryService:
    """Test suite for AsyncSalesforceQueryService."""

    async def test_query_path_and_params(self) -> None:
        """Validate query path and params."""
        content = _single_page([{"Id": "001AAA", "Name": "ACME"}])
        svc, transport = _make_async_service(content=content)
        result = await svc.query("SELECT Id, Name FROM Account LIMIT 1")
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/query")
        assert sent.params == {"q": "SELECT Id, Name FROM Account LIMIT 1"}
        assert isinstance(result, SalesforceQueryResponse)
        assert result.total_size == 1
        assert result.records[0]["Name"] == "ACME"

    async def test_query_uses_query_all_when_include_deleted(self) -> None:
        """Validate queryAll endpoint is used when include_deleted is set."""
        content = _single_page([{"Id": "001AAA", "IsDeleted": True}])
        svc, transport = _make_async_service(content=content)

        result = await svc.query(
            "SELECT Id, IsDeleted FROM Account",
            include_deleted=True,
        )

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/queryAll")
        assert sent.params == {"q": "SELECT Id, IsDeleted FROM Account"}
        assert result.records[0]["IsDeleted"] is True

    async def test_query_more_uses_next_records_url(self) -> None:
        """Validate query more uses next records url."""
        content = _single_page([{"Id": "001BBB", "Name": "Globex"}])
        next_url = f"/services/data/v{DEFAULT_API_VERSION}/query/01g...XXXX-2000"
        svc, transport = _make_async_service(content=content)
        result = await svc.query_more(next_url)
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(next_url)
        assert isinstance(result, SalesforceQueryResponse)
        assert result.records[0]["Name"] == "Globex"

    async def test_query_more_follows_query_all_next_records_url(self) -> None:
        """Validate query_more follows the server-provided queryAll URL."""
        content = _single_page([{"Id": "001BBB", "Name": "Globex"}])
        next_url = f"/services/data/v{DEFAULT_API_VERSION}/queryAll/01g...XXXX-2000"
        svc, transport = _make_async_service(content=content)

        result = await svc.query_more(next_url)

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(next_url)
        assert isinstance(result, SalesforceQueryResponse)
        assert result.records[0]["Name"] == "Globex"

    async def test_query_more_from_id_builds_query_path(self) -> None:
        """Validate async query_more_from_id builds the query cursor URL."""
        content = _single_page([{"Id": "001BBB", "Name": "Globex"}])
        svc, transport = _make_async_service(content=content)

        result = await svc.query_more_from_id("01g...XXXX-2000")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(
            f"/services/data/v{DEFAULT_API_VERSION}/query/01g...XXXX-2000"
        )
        assert result.records[0]["Name"] == "Globex"

    async def test_query_more_from_id_builds_query_all_path_when_requested(
        self,
    ) -> None:
        """Validate async query_more_from_id supports queryAll continuation."""
        content = _single_page([{"Id": "001BBB", "Name": "Globex"}])
        svc, transport = _make_async_service(content=content)

        _ = await svc.query_more_from_id("01g...XXXX-2000", include_deleted=True)

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(
            f"/services/data/v{DEFAULT_API_VERSION}/queryAll/01g...XXXX-2000"
        )

    async def test_query_more_from_id_rejects_full_path(self) -> None:
        """Validate async query_more_from_id rejects full URL fragments."""
        svc, _ = _make_async_service(content=_single_page([]))

        with pytest.raises(ValueError, match="cursor token"):
            await svc.query_more_from_id("/services/data/v59.0/query/01g")

    async def test_query_all_iter_single_page(self) -> None:
        """Validate query all iter single page."""
        records = [{"Id": "001AAA"}, {"Id": "001BBB"}]
        content = _single_page(records)
        svc, _ = _make_async_service(content=content)
        pages = [page async for page in svc.query_all_iter("SELECT Id FROM Account")]
        assert len(pages) == 1
        assert pages[0].records == records

    async def test_query_all_iter_paginates(self) -> None:
        """Validate query all iter paginates."""
        next_url = f"/services/data/v{DEFAULT_API_VERSION}/query/01g...XXXX-2000"
        page1 = _page_with_next([{"Id": "001AAA"}], next_url, total=2)
        page2 = _single_page([{"Id": "001BBB"}], total=2)

        transport = MockAsyncTransport(status_code=200, content=page1)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        svc = AsyncSalesforceQueryService(client)

        call_count = 0

        async def side_effect(_req: Any) -> Any:
            """Return side effect."""
            nonlocal call_count
            call_count += 1
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.content = page1 if call_count == 1 else page2
            return mock_resp

        transport.send.side_effect = side_effect

        pages = [page async for page in svc.query_all_iter("SELECT Id FROM Account")]
        assert len(pages) == 2
        assert pages[0].records == [{"Id": "001AAA"}]
        assert pages[1].records == [{"Id": "001BBB"}]

    async def test_query_all_returns_flat_list(self) -> None:
        """Validate query all returns flat list."""
        next_url = f"/services/data/v{DEFAULT_API_VERSION}/query/01g...XXXX-2000"
        page1 = _page_with_next([{"Id": "001AAA"}], next_url, total=2)
        page2 = _single_page([{"Id": "001BBB"}], total=2)

        transport = MockAsyncTransport(status_code=200, content=page1)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        svc = AsyncSalesforceQueryService(client)

        call_count = 0

        async def side_effect(_req: Any) -> Any:
            """Return side effect."""
            nonlocal call_count
            call_count += 1
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.content = page1 if call_count == 1 else page2
            return mock_resp

        transport.send.side_effect = side_effect

        records = await svc.query_all("SELECT Id FROM Account")
        assert records == [{"Id": "001AAA"}, {"Id": "001BBB"}]

    async def test_query_all_iter_uses_query_all_when_include_deleted(self) -> None:
        """Validate query_all_iter starts from queryAll when requested."""
        content = _single_page([{"Id": "001AAA", "IsDeleted": True}])
        svc, transport = _make_async_service(content=content)

        pages = [
            page
            async for page in svc.query_all_iter(
                "SELECT Id, IsDeleted FROM Account",
                include_deleted=True,
            )
        ]

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/queryAll")
        assert len(pages) == 1
        assert pages[0].records[0]["IsDeleted"] is True

    async def test_query_all_uses_query_all_when_include_deleted(self) -> None:
        """Validate query_all starts from queryAll when requested."""
        content = _single_page([{"Id": "001AAA", "IsDeleted": True}])
        svc, transport = _make_async_service(content=content)

        records = await svc.query_all(
            "SELECT Id, IsDeleted FROM Account",
            include_deleted=True,
        )

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/queryAll")
        assert records == [{"Id": "001AAA", "IsDeleted": True}]

    def test_facade_query_returns_service(self) -> None:
        """Validate facade query returns service."""
        transport = MockAsyncTransport(status_code=200, content=b"{}")
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        facade = AsyncSalesforceAPIFacade(client)
        svc = facade.query()
        assert isinstance(svc, AsyncSalesforceQueryService)

    async def test_parallel_query_resolves_api_version_once(
        self,
        monkeypatch: Any,
    ) -> None:
        """Parallel query calls resolve API version only once per service."""
        content = _single_page([{"Id": "001AAA"}])
        svc, _ = _make_async_service(content=content)
        call_count = 0

        async def fake_resolve(_client: Any, _api_version: str | None) -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0)
            return "63.0"

        monkeypatch.setattr(
            "plynth.connectors.salesforce.query.service.resolve_async_api_version",
            fake_resolve,
        )

        await asyncio.gather(
            svc.query("SELECT Id FROM Account LIMIT 1"),
            svc.query("SELECT Id FROM Contact LIMIT 1"),
        )

        assert call_count == 1

    async def test_parallel_query_mixed_include_deleted_resolves_once(
        self,
        monkeypatch: Any,
    ) -> None:
        """Mixed parallel query/queryAll calls resolve API version only once."""
        content = _single_page([{"Id": "001AAA"}])
        svc, transport = _make_async_service(content=content)
        call_count = 0

        async def fake_resolve(_client: Any, _api_version: str | None) -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0)
            return "63.0"

        monkeypatch.setattr(
            "plynth.connectors.salesforce.query.service.resolve_async_api_version",
            fake_resolve,
        )

        await asyncio.gather(
            svc.query("SELECT Id FROM Account LIMIT 1"),
            svc.query(
                "SELECT Id, IsDeleted FROM Account LIMIT 1",
                include_deleted=True,
            ),
        )

        assert call_count == 1

        urls = [call.args[0].url for call in transport.send.call_args_list]
        assert any("/services/data/v63.0/query" in url for url in urls)
        assert any("/services/data/v63.0/queryAll" in url for url in urls)


class TestSalesforceObjectQueryService:
    """Test suite for SalesforceObjectQueryService."""

    def test_facade_object_query_returns_service(self) -> None:
        """Validate facade object_query returns object-scoped service."""
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=BASE_URL, transport=transport)
        facade = SalesforceAPIFacade(client)

        svc = facade.object_query("Account")

        assert isinstance(svc, SalesforceObjectQueryService)

    def test_object_query_builds_soql_and_calls_query_endpoint(self) -> None:
        """Validate object query service composes SOQL for one object."""
        content = _single_page([{"Id": "001AAA", "Name": "ACME"}])
        transport = MockSyncTransport(status_code=200, content=content)
        client = APIClient(base_url=BASE_URL, transport=transport)
        svc = SalesforceObjectQueryService(client, "Account")

        _ = svc.query(fields=["Id", "Name"], where="IsDeleted = false", limit=1)

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/query")
        assert sent.params == {
            "q": "SELECT Id, Name FROM Account WHERE IsDeleted = false LIMIT 1"
        }

    def test_object_query_more_from_id(self) -> None:
        """Validate object query service delegates cursor continuation helper."""
        content = _single_page([{"Id": "001AAA"}])
        transport = MockSyncTransport(status_code=200, content=content)
        client = APIClient(base_url=BASE_URL, transport=transport)
        svc = SalesforceObjectQueryService(client, "Account")

        _ = svc.query_more_from_id("01g...XXXX-2000")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(
            f"/services/data/v{DEFAULT_API_VERSION}/query/01g...XXXX-2000"
        )

    def test_query_more_delegates_next_records_url(self) -> None:
        """query_more forwards the raw next-records URL to the underlying service."""
        content = _single_page([{"Id": "001AAA"}])
        transport = MockSyncTransport(status_code=200, content=content)
        client = APIClient(base_url=BASE_URL, transport=transport)
        svc = SalesforceObjectQueryService(client, "Account")
        next_url = f"/services/data/v{DEFAULT_API_VERSION}/query/01g...next"

        _ = svc.query_more(next_url)

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(next_url)

    def test_query_all_iter_builds_soql_and_yields_pages(self) -> None:
        """query_all_iter composes SOQL for the object and yields each response page."""
        content = _single_page([{"Id": "001AAA"}])
        transport = MockSyncTransport(status_code=200, content=content)
        client = APIClient(base_url=BASE_URL, transport=transport)
        svc = SalesforceObjectQueryService(client, "Account")

        pages = list(svc.query_all_iter(fields=["Id"], limit=1))

        assert len(pages) == 1
        sent = transport.send.call_args[0][0]
        assert sent.params == {"q": "SELECT Id FROM Account LIMIT 1"}

    def test_query_all_builds_soql_and_returns_flat_list(self) -> None:
        """query_all composes SOQL for the object and returns records as a flat list."""
        records = [{"Id": "001AAA"}, {"Id": "001BBB"}]
        content = _single_page(records)
        transport = MockSyncTransport(status_code=200, content=content)
        client = APIClient(base_url=BASE_URL, transport=transport)
        svc = SalesforceObjectQueryService(client, "Account")

        result = svc.query_all(fields=["Id"])

        assert result == records
        sent = transport.send.call_args[0][0]
        assert sent.params == {"q": "SELECT Id FROM Account"}

    def test_query_updated_since_builds_incremental_soql(self) -> None:
        """query_updated_since composes a deterministic incremental filter."""
        content = _single_page([{"Id": "001AAA"}])
        transport = MockSyncTransport(status_code=200, content=content)
        client = APIClient(base_url=BASE_URL, transport=transport)
        svc = SalesforceObjectQueryService(client, "Account")

        _ = svc.query_updated_since(
            datetime(2026, 5, 11, 10, 15, 0, tzinfo=UTC),
            fields=["Id", "SystemModstamp"],
            where="IsDeleted = false",
        )

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "FROM Account" in soql
        assert (
            "(IsDeleted = false) AND SystemModstamp >= '2026-05-11T10:15:00Z'" in soql
        )
        assert "ORDER BY SystemModstamp ASC" in soql

    def test_query_updated_since_rejects_naive_datetime(self) -> None:
        """query_updated_since rejects naive datetimes to avoid timezone ambiguity."""
        content = _single_page([{"Id": "001AAA"}])
        transport = MockSyncTransport(status_code=200, content=content)
        client = APIClient(base_url=BASE_URL, transport=transport)
        svc = SalesforceObjectQueryService(client, "Account")

        with pytest.raises(ValueError, match="timezone-aware"):
            _ = svc.query_updated_since(datetime(2026, 5, 11, 10, 15, 0))


class TestAsyncSalesforceObjectQueryService:
    """Test suite for AsyncSalesforceObjectQueryService."""

    def test_facade_object_query_returns_service(self) -> None:
        """Validate async facade object_query returns object-scoped service."""
        transport = MockAsyncTransport(status_code=200, content=b"{}")
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        facade = AsyncSalesforceAPIFacade(client)

        svc = facade.object_query("Account")

        assert isinstance(svc, AsyncSalesforceObjectQueryService)

    async def test_object_query_builds_soql_and_calls_query_endpoint(self) -> None:
        """Validate async object query service composes SOQL for one object."""
        content = _single_page([{"Id": "001AAA", "Name": "ACME"}])
        transport = MockAsyncTransport(status_code=200, content=content)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        svc = AsyncSalesforceObjectQueryService(client, "Account")

        _ = await svc.query(
            fields=["Id", "Name"],
            where="IsDeleted = false",
            limit=1,
        )

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/query")
        assert sent.params == {
            "q": "SELECT Id, Name FROM Account WHERE IsDeleted = false LIMIT 1"
        }

    async def test_object_query_more_delegates_next_records_url(self) -> None:
        """query_more forwards the raw next-records URL to the underlying service."""
        content = _single_page([{"Id": "001AAA"}])
        transport = MockAsyncTransport(status_code=200, content=content)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        svc = AsyncSalesforceObjectQueryService(client, "Account")
        next_url = f"/services/data/v{DEFAULT_API_VERSION}/query/01g...next"

        _ = await svc.query_more(next_url)

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(next_url)

    async def test_object_query_more_from_id_builds_query_path(self) -> None:
        """query_more_from_id delegates to the underlying service with the cursor ID."""
        content = _single_page([{"Id": "001AAA"}])
        transport = MockAsyncTransport(status_code=200, content=content)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        svc = AsyncSalesforceObjectQueryService(client, "Account")

        _ = await svc.query_more_from_id("01g...XXXX-2000")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(
            f"/services/data/v{DEFAULT_API_VERSION}/query/01g...XXXX-2000"
        )

    async def test_object_query_all_iter_yields_pages(self) -> None:
        """query_all_iter composes SOQL for the object and yields each response page."""
        content = _single_page([{"Id": "001AAA"}])
        transport = MockAsyncTransport(status_code=200, content=content)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        svc = AsyncSalesforceObjectQueryService(client, "Account")

        pages = [page async for page in svc.query_all_iter(fields=["Id"], limit=1)]

        assert len(pages) == 1
        sent = transport.send.call_args[0][0]
        assert sent.params == {"q": "SELECT Id FROM Account LIMIT 1"}

    async def test_object_query_all_returns_flat_list(self) -> None:
        """query_all composes SOQL for the object and returns records as a flat list."""
        records = [{"Id": "001AAA"}, {"Id": "001BBB"}]
        content = _single_page(records)
        transport = MockAsyncTransport(status_code=200, content=content)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        svc = AsyncSalesforceObjectQueryService(client, "Account")

        result = await svc.query_all(fields=["Id"])

        assert result == records
        sent = transport.send.call_args[0][0]
        assert sent.params == {"q": "SELECT Id FROM Account"}

    async def test_query_updated_since_builds_incremental_soql(self) -> None:
        """async query_updated_since composes a deterministic incremental filter."""
        content = _single_page([{"Id": "001AAA"}])
        transport = MockAsyncTransport(status_code=200, content=content)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        svc = AsyncSalesforceObjectQueryService(client, "Account")

        _ = await svc.query_updated_since(
            datetime(2026, 5, 11, 10, 15, 0, tzinfo=UTC),
            fields=["Id", "SystemModstamp"],
            where="IsDeleted = false",
        )

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "FROM Account" in soql
        assert (
            "(IsDeleted = false) AND SystemModstamp >= '2026-05-11T10:15:00Z'" in soql
        )
        assert "ORDER BY SystemModstamp ASC" in soql

    async def test_query_updated_since_rejects_naive_datetime(self) -> None:
        """async query_updated_since rejects naive datetimes."""
        content = _single_page([{"Id": "001AAA"}])
        transport = MockAsyncTransport(status_code=200, content=content)
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        svc = AsyncSalesforceObjectQueryService(client, "Account")

        with pytest.raises(ValueError, match="timezone-aware"):
            _ = await svc.query_updated_since(datetime(2026, 5, 11, 10, 15, 0))
