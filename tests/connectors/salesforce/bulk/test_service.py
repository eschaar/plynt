"""Tests for SalesforceBulkService and AsyncSalesforceBulkService."""

from __future__ import annotations

import json
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest

from plynth.base.response import Response
from plynth.connectors.salesforce.bulk import (
    AsyncSalesforceBulkService,
    BulkIngestResult,
    BulkJobInfo,
    BulkJobState,
    BulkOperation,
    SalesforceBulkService,
    _csv_to_records,
    _poll_delay,
    _records_to_csv,
)
from plynth.connectors.salesforce.constants import DEFAULT_API_VERSION
from plynth.connectors.salesforce.errors import (
    BulkJobTimeoutError,
    SalesforceBulkJobError,
)
from plynth.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynth.http.client import APIClient, AsyncAPIClient
from tests.conftest import MockAsyncTransport, MockSyncTransport

BASE_URL = "https://myorg.my.salesforce.com"
API_VERSION = "60.0"
JOB_ID = "7507A00000MbGHXQA3"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _job_payload(
    job_id: str = JOB_ID,
    operation: str = "insert",
    state: str = "Open",
    sobject: str = "Account",
    content_url: str | None = (
        "/services/data/v60.0/jobs/ingest/7507A00000MbGHXQA3/batches"
    ),
    error_message: str | None = None,
) -> bytes:
    """Return a minimal BulkJobInfo JSON payload."""
    data: dict[str, Any] = {
        "id": job_id,
        "operation": operation,
        "object": sobject,
        "state": state,
    }
    if content_url is not None:
        data["contentUrl"] = content_url
    if error_message is not None:
        data["errorMessage"] = error_message
    return json.dumps(data).encode()


def _make_service(
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[SalesforceBulkService, MockSyncTransport]:
    """Return a service backed by a single-response sync transport stub."""
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = APIClient(base_url=BASE_URL, transport=transport)
    return SalesforceBulkService(client, api_version=API_VERSION), transport


def _make_async_service(
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[AsyncSalesforceBulkService, MockAsyncTransport]:
    """Return a service backed by a single-response async transport stub."""
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
    return AsyncSalesforceBulkService(client, api_version=API_VERSION), transport


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


class TestRecordsToCsv:
    """Tests for _records_to_csv."""

    def test_single_record(self) -> None:
        """CSV for one record contains a header row and one data row."""
        result = _records_to_csv([{"Name": "Acme", "Industry": "Tech"}])
        lines = result.decode().splitlines()
        assert lines[0] == "Name,Industry"
        assert lines[1] == "Acme,Tech"

    def test_multiple_records(self) -> None:
        """All records are serialised, missing values become empty strings."""
        records = [
            {"Name": "Acme", "Industry": "Tech"},
            {"Name": "Globex"},
        ]
        result = _records_to_csv(records)
        lines = result.decode().splitlines()
        assert lines[0] == "Name,Industry"
        assert lines[1] == "Acme,Tech"
        assert lines[2] == "Globex,"

    def test_preserves_key_insertion_order(self) -> None:
        """Column order in the CSV matches first-encounter order across records."""
        records = [{"Z": "1", "A": "2"}, {"B": "3"}]
        result = _records_to_csv(records)
        header = result.decode().splitlines()[0]
        assert header == "Z,A,B"

    def test_empty_records_returns_empty_bytes(self) -> None:
        """Empty input produces no output."""
        assert _records_to_csv([]) == b""

    def test_returns_utf8_bytes(self) -> None:
        """Output is valid UTF-8 bytes."""
        result = _records_to_csv([{"Name": "Böse Corp"}])
        assert isinstance(result, bytes)
        result.decode("utf-8")


class TestCsvToRecords:
    """Tests for _csv_to_records."""

    def test_single_row(self) -> None:
        """A header plus one data row becomes a list with one dict."""
        result = _csv_to_records("Name,Industry\nAcme,Tech\n")
        assert result == [{"Name": "Acme", "Industry": "Tech"}]

    def test_multiple_rows(self) -> None:
        """Multiple data rows become multiple dicts."""
        csv_text = "Name,Industry\nAcme,Tech\nGlobex,Energy\n"
        result = _csv_to_records(csv_text)
        assert len(result) == 2
        assert result[1]["Name"] == "Globex"

    def test_strips_null_bytes(self) -> None:
        """Embedded null bytes are removed before parsing."""
        result = _csv_to_records("Name\nAc\x00me\n")
        assert result == [{"Name": "Acme"}]

    def test_empty_input(self) -> None:
        """Empty or whitespace-only input returns an empty list."""
        assert _csv_to_records("") == []
        assert _csv_to_records("   \n") == []


class TestPollDelay:
    """Tests for _poll_delay."""

    def test_first_attempt_is_half_second(self) -> None:
        """Attempt 0 returns the initial 0.5 s delay."""
        assert _poll_delay(0) == pytest.approx(0.5)

    def test_delay_doubles_each_attempt(self) -> None:
        """Delay doubles from attempt 0 to 1."""
        assert _poll_delay(1) == pytest.approx(1.0)

    def test_delay_is_capped_at_two_seconds(self) -> None:
        """Delay never exceeds 2.0 s regardless of the attempt number."""
        for attempt in range(5, 20):
            assert _poll_delay(attempt) == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestBulkJobInfo:
    """Tests for BulkJobInfo model validation."""

    def test_minimal_payload(self) -> None:
        """A minimal JSON payload with required fields is accepted."""
        data = {
            "id": JOB_ID,
            "operation": "insert",
            "object": "Account",
            "state": "Open",
        }
        job = BulkJobInfo.model_validate(data)
        assert job.id == JOB_ID
        assert job.sobject == "Account"
        assert job.state is BulkJobState.open

    def test_all_fields(self) -> None:
        """All documented fields are parsed correctly."""
        data = {
            "id": JOB_ID,
            "operation": "upsert",
            "object": "Contact",
            "state": "JobComplete",
            "contentUrl": "/services/data/v60.0/jobs/ingest/abc/batches",
            "apiVersion": 60.0,
            "numberRecordsProcessed": 500,
            "numberRecordsFailed": 3,
            "errorMessage": None,
        }
        job = BulkJobInfo.model_validate(data)
        assert job.operation == "upsert"
        assert job.content_url == "/services/data/v60.0/jobs/ingest/abc/batches"
        assert job.number_records_processed == 500
        assert job.state is BulkJobState.job_complete

    def test_object_alias_maps_to_sobject(self) -> None:
        """The Salesforce JSON key ``object`` maps to the ``sobject`` attribute."""
        data = {
            "id": JOB_ID,
            "operation": "delete",
            "object": "Lead",
            "state": "Open",
        }
        job = BulkJobInfo.model_validate(data)
        assert job.sobject == "Lead"


class TestBulkIngestResult:
    """Tests for BulkIngestResult model defaults."""

    def test_defaults_to_empty_lists(self) -> None:
        """All three lists default to empty."""
        result = BulkIngestResult()
        assert result.successful == []
        assert result.failed == []
        assert result.unprocessed == []


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------


class TestSalesforceBulkJobError:
    """Tests for SalesforceBulkJobError."""

    def test_message_includes_job_id(self) -> None:
        """Exception message contains the job ID."""
        exc = SalesforceBulkJobError(job_id="abc123", message="something went wrong")
        assert "abc123" in str(exc)
        assert "something went wrong" in str(exc)

    def test_attributes(self) -> None:
        """job_id, errors, and status_code are set correctly."""
        exc = SalesforceBulkJobError(job_id="abc123", message="err")
        assert exc.job_id == "abc123"
        assert exc.errors == []
        assert exc.status_code == 0

    def test_is_subclass_of_salesforce_api_error(self) -> None:
        """Inherits from SalesforceAPIError for unified exception handling."""
        from plynth.connectors.salesforce.errors import SalesforceAPIError

        exc = SalesforceBulkJobError(job_id="x", message="y")
        assert isinstance(exc, SalesforceAPIError)


class TestBulkJobTimeoutError:
    """Tests for BulkJobTimeoutError."""

    def test_message_includes_job_id_and_duration(self) -> None:
        """Exception message contains the job ID and max_wait seconds."""
        exc = BulkJobTimeoutError(job_id="abc123", max_wait=30.0)
        assert "abc123" in str(exc)
        assert "30.0" in str(exc)

    def test_attributes(self) -> None:
        """job_id, max_wait, errors, and status_code are set correctly."""
        exc = BulkJobTimeoutError(job_id="abc123", max_wait=15.0)
        assert exc.job_id == "abc123"
        assert exc.max_wait == pytest.approx(15.0)
        assert exc.errors == []
        assert exc.status_code == 0


# ---------------------------------------------------------------------------
# SalesforceBulkService
# ---------------------------------------------------------------------------


class TestSalesforceBulkService:
    """Tests for SalesforceBulkService."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _service_with_states(self, *states: str) -> SalesforceBulkService:
        """Return a service whose transport responds with sequential job states."""
        transport = MockSyncTransport()
        transport.send.side_effect = [
            Response(status_code=200, content=_job_payload(state=s)) for s in states
        ]
        client = APIClient(base_url=BASE_URL, transport=transport)
        return SalesforceBulkService(client, api_version=API_VERSION)

    def test_init_resolves_api_version_from_client_when_not_provided(self) -> None:
        """When omitted, sync service resolves version from client.api_version."""
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=BASE_URL, transport=transport)
        cast(Any, client).api_version = "62.0"

        service = SalesforceBulkService(client)

        assert service._api_version == "62.0"

    def test_init_falls_back_to_default_api_version_when_unresolved(self) -> None:
        """When unresolved, sync service falls back to DEFAULT_API_VERSION."""
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=BASE_URL, transport=transport)

        service = SalesforceBulkService(client)

        assert service._api_version == DEFAULT_API_VERSION

    def _make_happy_path_transport(self) -> MockSyncTransport:
        """Return a transport that succeeds through the full ingest lifecycle."""
        successful_csv = "sf__Id,sf__Created,Name\nabc,true,Acme\n"
        transport = MockSyncTransport()
        transport.send.side_effect = [
            # create_ingest_job
            Response(status_code=200, content=_job_payload(state="Open")),
            # upload_records (PUT -> 201)
            Response(status_code=201, content=b""),
            # close_job
            Response(status_code=200, content=_job_payload(state="UploadComplete")),
            # wait_for_job: get_job polls
            Response(status_code=200, content=_job_payload(state="JobComplete")),
            # get_ingest_results: successful, failed, unprocessed
            Response(status_code=200, content=successful_csv.encode()),
            Response(status_code=200, content=b""),
            Response(status_code=200, content=b""),
        ]
        return transport

    # ------------------------------------------------------------------
    # create_ingest_job
    # ------------------------------------------------------------------

    def test_create_ingest_job_returns_bulk_job_info(self) -> None:
        """A successful POST returns a parsed BulkJobInfo."""
        service, _ = _make_service(
            status_code=200,
            content=_job_payload(state="Open"),
        )
        job = service.create_ingest_job("Account", BulkOperation.insert)
        assert isinstance(job, BulkJobInfo)
        assert job.id == JOB_ID
        assert job.state is BulkJobState.open

    def test_create_ingest_job_request_body(self) -> None:
        """POST body includes the operation, object, and contentType."""
        service, transport = _make_service(content=_job_payload())
        service.create_ingest_job("Account", BulkOperation.insert)
        raw = transport.send.call_args[0][0].content
        body = json.loads(raw)
        assert body["operation"] == "insert"
        assert body["object"] == "Account"
        assert body["contentType"] == "CSV"

    def test_create_ingest_job_upsert_includes_external_id_field(self) -> None:
        """Upsert requests include the externalIdFieldName in the body."""
        service, transport = _make_service(content=_job_payload(operation="upsert"))
        service.create_ingest_job(
            "Contact", BulkOperation.upsert, external_id_field="Email__c"
        )
        raw = transport.send.call_args[0][0].content
        body = json.loads(raw)
        assert body["externalIdFieldName"] == "Email__c"

    def test_create_ingest_job_upsert_without_external_id_raises(self) -> None:
        """Upsert without external_id_field raises ValueError before any HTTP call."""
        service, _ = _make_service()
        with pytest.raises(ValueError, match="external_id_field"):
            service.create_ingest_job("Contact", BulkOperation.upsert)

    def test_create_ingest_job_posts_to_ingest_endpoint(self) -> None:
        """Request is sent to the /jobs/ingest path."""
        service, transport = _make_service(content=_job_payload())
        service.create_ingest_job("Account", BulkOperation.insert)
        path = transport.send.call_args[0][0].url
        assert "/jobs/ingest" in path
        assert API_VERSION in path

    # ------------------------------------------------------------------
    # create_query_job
    # ------------------------------------------------------------------

    def test_create_query_job_returns_bulk_job_info(self) -> None:
        """A successful POST returns a parsed BulkJobInfo in InProgress state."""
        service, _ = _make_service(
            content=_job_payload(state="InProgress", operation="query"),
        )
        job = service.create_query_job("SELECT Id FROM Account")
        assert job.state is BulkJobState.in_progress

    def test_create_query_job_uses_query_operation_by_default(self) -> None:
        """Without include_deleted, the operation is ``query``."""
        service, transport = _make_service(
            content=_job_payload(operation="query", state="InProgress"),
        )
        service.create_query_job("SELECT Id FROM Account")
        body = json.loads(transport.send.call_args[0][0].content)
        assert body["operation"] == "query"

    def test_create_query_job_include_deleted_uses_query_all(self) -> None:
        """With include_deleted=True, the operation is ``queryAll``."""
        service, transport = _make_service(
            content=_job_payload(operation="queryAll", state="InProgress"),
        )
        service.create_query_job("SELECT Id FROM Account", include_deleted=True)
        body = json.loads(transport.send.call_args[0][0].content)
        assert body["operation"] == "queryAll"

    def test_create_query_job_posts_to_query_endpoint(self) -> None:
        """Request is sent to the /jobs/query path."""
        service, transport = _make_service(
            content=_job_payload(operation="query", state="InProgress"),
        )
        service.create_query_job("SELECT Id FROM Account")
        path = transport.send.call_args[0][0].url
        assert "/jobs/query" in path

    # ------------------------------------------------------------------
    # get_job
    # ------------------------------------------------------------------

    def test_get_job_ingest_uses_ingest_path(self) -> None:
        """is_query=False sends a GET to the /jobs/ingest path."""
        service, transport = _make_service(content=_job_payload())
        service.get_job(JOB_ID, is_query=False)
        path = transport.send.call_args[0][0].url
        assert f"/jobs/ingest/{JOB_ID}" in path

    def test_get_job_query_uses_query_path(self) -> None:
        """is_query=True sends a GET to the /jobs/query path."""
        service, transport = _make_service(
            content=_job_payload(state="InProgress", operation="query"),
        )
        service.get_job(JOB_ID, is_query=True)
        path = transport.send.call_args[0][0].url
        assert f"/jobs/query/{JOB_ID}" in path

    # ------------------------------------------------------------------
    # upload_records
    # ------------------------------------------------------------------

    def test_upload_records_sends_csv_to_content_url(self) -> None:
        """Records are serialised to CSV and PUT to the given content_url."""
        service, transport = _make_service(status_code=201, content=b"")
        service.upload_records(
            JOB_ID,
            [{"Name": "Acme"}],
            content_url="/services/data/v60.0/jobs/ingest/abc/batches",
        )
        req = transport.send.call_args[0][0]
        assert "Name" in req.content.decode()
        assert req.headers.get("Content-Type", "").startswith("text/csv")

    def test_upload_records_uses_default_path_when_no_content_url(self) -> None:
        """When content_url is None, the path is derived from job_id."""
        service, transport = _make_service(status_code=201, content=b"")
        service.upload_records(JOB_ID, [{"Name": "Acme"}])
        path = transport.send.call_args[0][0].url
        assert f"/jobs/ingest/{JOB_ID}/batches" in path

    def test_upload_records_empty_raises(self) -> None:
        """An empty records list raises ValueError before any HTTP call."""
        service, _ = _make_service()
        with pytest.raises(ValueError, match="empty"):
            service.upload_records(JOB_ID, [])

    def test_upload_records_oversized_payload_raises(self) -> None:
        """Payloads exceeding 100 MB raise ValueError before sending."""
        service, _ = _make_service()
        large_value = "x" * (110 * 1024 * 1024)
        records = [{"data": large_value}]
        with pytest.raises(ValueError, match="100 MB"):
            service.upload_records(JOB_ID, records)

    # ------------------------------------------------------------------
    # close_job
    # ------------------------------------------------------------------

    def test_close_job_patches_state_to_upload_complete(self) -> None:
        """PATCH body sets state to UploadComplete."""
        service, transport = _make_service(
            content=_job_payload(state="UploadComplete"),
        )
        job = service.close_job(JOB_ID)
        body = json.loads(transport.send.call_args[0][0].content)
        assert body["state"] == "UploadComplete"
        assert job.state is BulkJobState.upload_complete

    # ------------------------------------------------------------------
    # abort_job
    # ------------------------------------------------------------------

    def test_abort_job_ingest_patches_ingest_path(self) -> None:
        """Aborting an ingest job PATCHes the /jobs/ingest path."""
        service, transport = _make_service(content=_job_payload(state="Aborted"))
        job = service.abort_job(JOB_ID, is_query=False)
        path = transport.send.call_args[0][0].url
        assert f"/jobs/ingest/{JOB_ID}" in path
        assert job.state is BulkJobState.aborted

    def test_abort_job_query_patches_query_path(self) -> None:
        """Aborting a query job PATCHes the /jobs/query path."""
        service, transport = _make_service(
            content=_job_payload(state="Aborted", operation="query"),
        )
        service.abort_job(JOB_ID, is_query=True)
        path = transport.send.call_args[0][0].url
        assert f"/jobs/query/{JOB_ID}" in path

    # ------------------------------------------------------------------
    # delete_job
    # ------------------------------------------------------------------

    def test_delete_job_sends_delete_to_ingest_path(self) -> None:
        """Deleting an ingest job sends DELETE to /jobs/ingest/{id}."""
        service, transport = _make_service(status_code=204, content=b"")
        service.delete_job(JOB_ID, is_query=False)
        req = transport.send.call_args[0][0]
        assert req.method == "DELETE"
        assert f"/jobs/ingest/{JOB_ID}" in req.url

    def test_delete_job_sends_delete_to_query_path(self) -> None:
        """Deleting a query job sends DELETE to /jobs/query/{id}."""
        service, transport = _make_service(status_code=204, content=b"")
        service.delete_job(JOB_ID, is_query=True)
        req = transport.send.call_args[0][0]
        assert f"/jobs/query/{JOB_ID}" in req.url

    # ------------------------------------------------------------------
    # wait_for_job
    # ------------------------------------------------------------------

    def test_wait_for_job_returns_when_complete(self) -> None:
        """Returns the job info when state reaches JobComplete."""
        service = self._service_with_states("InProgress", "JobComplete")
        with patch("plynth.connectors.salesforce.bulk.service.time.sleep"):
            job = service.wait_for_job(JOB_ID, is_query=False)
        assert job.state is BulkJobState.job_complete

    def test_wait_for_job_raises_on_failed_state(self) -> None:
        """Raises SalesforceBulkJobError when job ends in Failed state."""
        service = self._service_with_states("InProgress", "Failed")
        with patch("plynth.connectors.salesforce.bulk.service.time.sleep"):
            with pytest.raises(SalesforceBulkJobError) as exc_info:
                service.wait_for_job(JOB_ID, is_query=False)
        assert exc_info.value.job_id == JOB_ID

    def test_wait_for_job_raises_on_aborted_state(self) -> None:
        """Raises SalesforceBulkJobError when job ends in Aborted state."""
        service = self._service_with_states("Aborted")
        with patch("plynth.connectors.salesforce.bulk.service.time.sleep"):
            with pytest.raises(SalesforceBulkJobError):
                service.wait_for_job(JOB_ID, is_query=False)

    def test_wait_for_job_raises_timeout(self) -> None:
        """Raises BulkJobTimeoutError when max_wait seconds elapse."""
        service = self._service_with_states("InProgress", "InProgress", "InProgress")
        with (
            patch("plynth.connectors.salesforce.bulk.service.time.sleep"),
            patch(
                "plynth.connectors.salesforce.bulk.service.time.monotonic",
                side_effect=[0.0, 0.1, 100.0],
            ),
        ):
            with pytest.raises(BulkJobTimeoutError) as exc_info:
                service.wait_for_job(JOB_ID, is_query=False, max_wait=30.0)
        assert exc_info.value.max_wait == pytest.approx(30.0)

    # ------------------------------------------------------------------
    # get_ingest_results
    # ------------------------------------------------------------------

    def test_get_ingest_results_returns_parsed_buckets(self) -> None:
        """Three result CSV endpoints are fetched and returned as BulkIngestResult."""
        successful_csv = "sf__Id,sf__Created,Name\nabc,true,Acme\n"
        failed_csv = "sf__Id,sf__Error,Name\n,DuplicateError,Globex\n"

        transport = MockSyncTransport()
        transport.send.side_effect = [
            Response(status_code=200, content=successful_csv.encode()),
            Response(status_code=200, content=failed_csv.encode()),
            Response(status_code=200, content=b""),  # unprocessed
        ]
        client = APIClient(base_url=BASE_URL, transport=transport)
        service = SalesforceBulkService(client, api_version=API_VERSION)

        result = service.get_ingest_results(JOB_ID)
        assert isinstance(result, BulkIngestResult)
        assert len(result.successful) == 1
        assert result.successful[0]["Name"] == "Acme"
        assert len(result.failed) == 1
        assert result.unprocessed == []

    # ------------------------------------------------------------------
    # get_query_results
    # ------------------------------------------------------------------

    def test_get_query_results_single_page(self) -> None:
        """A single page with no Sforce-Locator returns all records."""
        csv_content = "Id,Name\nAAA,Acme\n"
        transport = MockSyncTransport()
        transport.send.return_value = Response(
            status_code=200,
            content=csv_content.encode(),
            headers={},
        )
        client = APIClient(base_url=BASE_URL, transport=transport)
        service = SalesforceBulkService(client, api_version=API_VERSION)

        records = service.get_query_results(JOB_ID)
        assert records == [{"Id": "AAA", "Name": "Acme"}]

    def test_get_query_results_multi_page_pagination(self) -> None:
        """Pages are fetched until Sforce-Locator is absent or 'null'."""
        page1 = "Id,Name\nAAA,Acme\n"
        page2 = "Id,Name\nBBB,Globex\n"

        transport = MockSyncTransport()
        transport.send.side_effect = [
            Response(
                status_code=200,
                content=page1.encode(),
                headers={"Sforce-Locator": "abc"},
            ),
            Response(
                status_code=200,
                content=page2.encode(),
                headers={"Sforce-Locator": "null"},
            ),
        ]
        client = APIClient(base_url=BASE_URL, transport=transport)
        service = SalesforceBulkService(client, api_version=API_VERSION)

        records = service.get_query_results(JOB_ID)
        assert len(records) == 2
        assert records[0]["Name"] == "Acme"
        assert records[1]["Name"] == "Globex"

    def test_get_query_results_stops_on_empty_locator(self) -> None:
        """Pagination stops when the locator header is absent."""
        csv_content = "Id,Name\nAAA,Acme\n"
        transport = MockSyncTransport()
        transport.send.return_value = Response(
            status_code=200,
            content=csv_content.encode(),
            headers={},
        )
        client = APIClient(base_url=BASE_URL, transport=transport)
        service = SalesforceBulkService(client, api_version=API_VERSION)

        records = service.get_query_results(JOB_ID)
        assert len(records) == 1
        assert transport.send.call_count == 1

    # ------------------------------------------------------------------
    # ingest
    # ------------------------------------------------------------------

    def test_ingest_full_lifecycle(self) -> None:
        """A successful ingest runs all lifecycle steps and returns BulkIngestResult."""
        transport = self._make_happy_path_transport()
        client = APIClient(base_url=BASE_URL, transport=transport)
        service = SalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.time.sleep"):
            result = service.ingest("Account", BulkOperation.insert, [{"Name": "Acme"}])

        assert isinstance(result, BulkIngestResult)
        assert len(result.successful) == 1

    def test_ingest_empty_records_raises(self) -> None:
        """Empty records list raises ValueError without making any HTTP calls."""
        service, transport = _make_service()
        with pytest.raises(ValueError, match="empty"):
            service.ingest("Account", BulkOperation.insert, [])
        transport.send.assert_not_called()

    def test_ingest_aborts_job_on_upload_failure(self) -> None:
        """When upload fails, the service attempts to abort the job."""
        transport = MockSyncTransport()
        transport.send.side_effect = [
            # create_ingest_job succeeds
            Response(status_code=200, content=_job_payload(state="Open")),
            # upload_records raises (simulated by making send raise)
            RuntimeError("network failure"),
        ]
        client = APIClient(base_url=BASE_URL, transport=transport)
        service = SalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.time.sleep"):
            with pytest.raises(RuntimeError):
                service.ingest("Account", BulkOperation.insert, [{"Name": "Acme"}])

        # The cleanup path calls get_job then abort_job; total call count > 2
        assert transport.send.call_count >= 2

    def test_ingest_aborts_job_on_wait_failure(self) -> None:
        """When wait_for_job fails, the service aborts the job if still abortable."""
        transport = MockSyncTransport()
        transport.send.side_effect = [
            # create_ingest_job
            Response(status_code=200, content=_job_payload(state="Open")),
            # upload_records
            Response(status_code=201, content=b""),
            # close_job
            Response(status_code=200, content=_job_payload(state="UploadComplete")),
            # wait_for_job -> job ended in Failed state
            Response(status_code=200, content=_job_payload(state="Failed")),
            # cleanup: get_job (abortable check) -- already failed, not abortable
            Response(status_code=200, content=_job_payload(state="Failed")),
        ]
        client = APIClient(base_url=BASE_URL, transport=transport)
        service = SalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.time.sleep"):
            with pytest.raises(SalesforceBulkJobError):
                service.ingest("Account", BulkOperation.insert, [{"Name": "Acme"}])

    def test_ingest_aborts_job_when_still_abortable_after_failure(self) -> None:
        """Abort is issued when the job is still in an abortable state at cleanup."""
        transport = MockSyncTransport()
        transport.send.side_effect = [
            # create_ingest_job
            Response(status_code=200, content=_job_payload(state="Open")),
            # upload_records
            Response(status_code=201, content=b""),
            # close_job raises
            RuntimeError("close failed"),
            # cleanup: get_job -> still Open (abortable)
            Response(status_code=200, content=_job_payload(state="Open")),
            # abort_job
            Response(status_code=200, content=_job_payload(state="Aborted")),
        ]
        client = APIClient(base_url=BASE_URL, transport=transport)
        service = SalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.time.sleep"):
            with pytest.raises(RuntimeError):
                service.ingest("Account", BulkOperation.insert, [{"Name": "Acme"}])

        assert transport.send.call_count == 5

    # ------------------------------------------------------------------
    # query
    # ------------------------------------------------------------------

    def test_query_full_lifecycle(self) -> None:
        """A successful query runs all lifecycle steps and returns records."""
        csv_content = "Id,Name\nAAA,Acme\n"
        transport = MockSyncTransport()
        transport.send.side_effect = [
            # create_query_job
            Response(
                status_code=200,
                content=_job_payload(state="InProgress", operation="query"),
            ),
            # wait_for_job: get_job
            Response(
                status_code=200,
                content=_job_payload(state="JobComplete", operation="query"),
            ),
            # get_query_results
            Response(status_code=200, content=csv_content.encode(), headers={}),
        ]
        client = APIClient(base_url=BASE_URL, transport=transport)
        service = SalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.time.sleep"):
            records = service.query("SELECT Id, Name FROM Account")

        assert records == [{"Id": "AAA", "Name": "Acme"}]

    def test_query_aborts_job_on_failure(self) -> None:
        """When the query job fails, the service attempts to abort it."""
        transport = MockSyncTransport()
        transport.send.side_effect = [
            # create_query_job
            Response(
                status_code=200,
                content=_job_payload(state="InProgress", operation="query"),
            ),
            # wait_for_job -> Failed
            Response(
                status_code=200,
                content=_job_payload(state="Failed", operation="query"),
            ),
            # cleanup: get_job (Failed -- not abortable, abort skipped)
            Response(
                status_code=200,
                content=_job_payload(state="Failed", operation="query"),
            ),
        ]
        client = APIClient(base_url=BASE_URL, transport=transport)
        service = SalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.time.sleep"):
            with pytest.raises(SalesforceBulkJobError):
                service.query("SELECT Id FROM Account")

    def test_query_aborts_job_when_still_abortable_after_failure(self) -> None:
        """Abort is issued when the query job is still abortable at cleanup."""
        transport = MockSyncTransport()
        transport.send.side_effect = [
            # create_query_job
            Response(
                status_code=200,
                content=_job_payload(state="InProgress", operation="query"),
            ),
            # wait_for_job raises a generic error
            RuntimeError("poll failed"),
            # cleanup: get_job -> still InProgress (abortable)
            Response(
                status_code=200,
                content=_job_payload(state="InProgress", operation="query"),
            ),
            # abort_job
            Response(
                status_code=200,
                content=_job_payload(state="Aborted", operation="query"),
            ),
        ]
        client = APIClient(base_url=BASE_URL, transport=transport)
        service = SalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.time.sleep"):
            with pytest.raises(RuntimeError):
                service.query("SELECT Id FROM Account")

        assert transport.send.call_count == 4

    def test_query_silences_cleanup_error_and_reraises_original(self) -> None:
        """When get_job raises during cleanup, the original error is re-raised."""
        transport = MockSyncTransport()
        transport.send.side_effect = [
            # create_query_job
            Response(
                status_code=200,
                content=_job_payload(state="InProgress", operation="query"),
            ),
            # wait_for_job raises original error
            RuntimeError("original error"),
            # cleanup: get_job also raises
            RuntimeError("cleanup error"),
        ]
        client = APIClient(base_url=BASE_URL, transport=transport)
        service = SalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.time.sleep"):
            with pytest.raises(RuntimeError, match="original error"):
                service.query("SELECT Id FROM Account")


# ---------------------------------------------------------------------------
# AsyncSalesforceBulkService
# ---------------------------------------------------------------------------


class TestAsyncSalesforceBulkService:
    """Tests for AsyncSalesforceBulkService."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _async_service_with_states(self, *states: str) -> AsyncSalesforceBulkService:
        """Return an async service whose transport responds with sequential states."""
        transport = MockAsyncTransport()
        transport.send = AsyncMock(
            side_effect=[
                Response(status_code=200, content=_job_payload(state=s)) for s in states
            ]
        )
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        return AsyncSalesforceBulkService(client, api_version=API_VERSION)

    @pytest.mark.asyncio
    async def test_dynamic_version_resolves_from_client_get_api_version(self) -> None:
        """Async service resolves version lazily via client.get_api_version()."""
        transport = MockAsyncTransport(
            status_code=200, content=_job_payload(state="Open")
        )
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        cast(Any, client).get_api_version = AsyncMock(return_value="63.0")
        service = AsyncSalesforceBulkService(client)

        await service.create_ingest_job("Account", BulkOperation.insert)

        sent = transport.send.call_args[0][0]
        assert "/services/data/v63.0/jobs/ingest" in sent.url

    @pytest.mark.asyncio
    async def test_dynamic_version_falls_back_to_default_when_unresolved(self) -> None:
        """Async service falls back to DEFAULT_API_VERSION when unresolved."""
        transport = MockAsyncTransport(
            status_code=200, content=_job_payload(state="Open")
        )
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        cast(Any, client).get_api_version = AsyncMock(return_value="")
        service = AsyncSalesforceBulkService(client)

        await service.create_ingest_job("Account", BulkOperation.insert)

        sent = transport.send.call_args[0][0]
        assert f"/services/data/v{DEFAULT_API_VERSION}/jobs/ingest" in sent.url

    # ------------------------------------------------------------------
    # create_ingest_job
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_ingest_job_returns_bulk_job_info(self) -> None:
        """A successful POST returns a parsed BulkJobInfo."""
        service, _ = _make_async_service(content=_job_payload(state="Open"))
        job = await service.create_ingest_job("Account", BulkOperation.insert)
        assert isinstance(job, BulkJobInfo)
        assert job.state is BulkJobState.open

    @pytest.mark.asyncio
    async def test_create_ingest_job_upsert_without_external_id_raises(self) -> None:
        """Async upsert without external_id_field raises ValueError."""
        service, _ = _make_async_service()
        with pytest.raises(ValueError, match="external_id_field"):
            await service.create_ingest_job("Contact", BulkOperation.upsert)

    @pytest.mark.asyncio
    async def test_create_ingest_job_upsert_includes_external_id_field(self) -> None:
        """Async upsert requests include externalIdFieldName in the POST body."""
        service, transport = _make_async_service(
            content=_job_payload(operation="upsert")
        )
        await service.create_ingest_job(
            "Contact", BulkOperation.upsert, external_id_field="Email__c"
        )
        body = json.loads(transport.send.call_args[0][0].content)
        assert body["externalIdFieldName"] == "Email__c"

    # ------------------------------------------------------------------
    # upload_records
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_upload_records_sends_csv_content_type(self) -> None:
        """PUT request uses text/csv content type."""
        service, transport = _make_async_service(status_code=201, content=b"")
        await service.upload_records(JOB_ID, [{"Name": "Acme"}])
        req = transport.send.call_args[0][0]
        assert req.headers.get("Content-Type", "").startswith("text/csv")

    @pytest.mark.asyncio
    async def test_upload_records_empty_raises(self) -> None:
        """Empty records list raises ValueError without making any HTTP calls."""
        service, transport = _make_async_service()
        with pytest.raises(ValueError, match="empty"):
            await service.upload_records(JOB_ID, [])
        transport.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_records_oversized_payload_raises(self) -> None:
        """Payloads exceeding 100 MB raise ValueError before sending."""
        service, _ = _make_async_service()
        large_value = "x" * (110 * 1024 * 1024)
        with pytest.raises(ValueError, match="100 MB"):
            await service.upload_records(JOB_ID, [{"data": large_value}])

    # ------------------------------------------------------------------
    # abort_job
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_abort_job_patches_ingest_path(self) -> None:
        """Aborting an async ingest job PATCHes the /jobs/ingest path."""
        service, transport = _make_async_service(content=_job_payload(state="Aborted"))
        job = await service.abort_job(JOB_ID, is_query=False)
        path = transport.send.call_args[0][0].url
        assert f"/jobs/ingest/{JOB_ID}" in path
        assert job.state is BulkJobState.aborted

    @pytest.mark.asyncio
    async def test_abort_job_patches_query_path(self) -> None:
        """Aborting an async query job PATCHes the /jobs/query path."""
        service, transport = _make_async_service(
            content=_job_payload(state="Aborted", operation="query")
        )
        await service.abort_job(JOB_ID, is_query=True)
        path = transport.send.call_args[0][0].url
        assert f"/jobs/query/{JOB_ID}" in path

    # ------------------------------------------------------------------
    # delete_job
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_job_sends_delete_to_ingest_path(self) -> None:
        """Deleting an async ingest job sends DELETE to /jobs/ingest/{id}."""
        service, transport = _make_async_service(status_code=204, content=b"")
        await service.delete_job(JOB_ID, is_query=False)
        req = transport.send.call_args[0][0]
        assert req.method == "DELETE"
        assert f"/jobs/ingest/{JOB_ID}" in req.url

    @pytest.mark.asyncio
    async def test_delete_job_sends_delete_to_query_path(self) -> None:
        """Deleting an async query job sends DELETE to /jobs/query/{id}."""
        service, transport = _make_async_service(status_code=204, content=b"")
        await service.delete_job(JOB_ID, is_query=True)
        req = transport.send.call_args[0][0]
        assert f"/jobs/query/{JOB_ID}" in req.url

    # ------------------------------------------------------------------
    # wait_for_job
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_wait_for_job_returns_when_complete(self) -> None:
        """Returns the job info when state reaches JobComplete."""
        service = self._async_service_with_states("InProgress", "JobComplete")
        with patch("plynth.connectors.salesforce.bulk.service.asyncio.sleep"):
            job = await service.wait_for_job(JOB_ID, is_query=False)
        assert job.state is BulkJobState.job_complete

    @pytest.mark.asyncio
    async def test_wait_for_job_raises_on_failed_state(self) -> None:
        """Raises SalesforceBulkJobError when job ends in Failed state."""
        service = self._async_service_with_states("Failed")
        with patch("plynth.connectors.salesforce.bulk.service.asyncio.sleep"):
            with pytest.raises(SalesforceBulkJobError) as exc_info:
                await service.wait_for_job(JOB_ID, is_query=False)
        assert exc_info.value.job_id == JOB_ID

    @pytest.mark.asyncio
    async def test_wait_for_job_raises_timeout(self) -> None:
        """Raises BulkJobTimeoutError when max_wait is exceeded."""
        service = self._async_service_with_states(
            "InProgress", "InProgress", "InProgress"
        )
        with (
            patch("plynth.connectors.salesforce.bulk.service.asyncio.sleep"),
            patch(
                "plynth.connectors.salesforce.bulk.service.time.monotonic",
                side_effect=[0.0, 0.1, 100.0],
            ),
        ):
            with pytest.raises(BulkJobTimeoutError):
                await service.wait_for_job(JOB_ID, is_query=False, max_wait=30.0)

    # ------------------------------------------------------------------
    # ingest
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ingest_full_lifecycle(self) -> None:
        """A successful async ingest runs all lifecycle steps."""
        successful_csv = "sf__Id,sf__Created,Name\nabc,true,Acme\n"
        transport = MockAsyncTransport()
        transport.send = AsyncMock(
            side_effect=[
                Response(status_code=200, content=_job_payload(state="Open")),
                Response(status_code=201, content=b""),
                Response(
                    status_code=200,
                    content=_job_payload(state="UploadComplete"),
                ),
                Response(status_code=200, content=_job_payload(state="JobComplete")),
                Response(status_code=200, content=successful_csv.encode()),
                Response(status_code=200, content=b""),
                Response(status_code=200, content=b""),
            ]
        )
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        service = AsyncSalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.asyncio.sleep"):
            result = await service.ingest(
                "Account", BulkOperation.insert, [{"Name": "Acme"}]
            )

        assert isinstance(result, BulkIngestResult)
        assert len(result.successful) == 1

    @pytest.mark.asyncio
    async def test_ingest_empty_records_raises(self) -> None:
        """Empty records list raises ValueError."""
        service, transport = _make_async_service()
        with pytest.raises(ValueError, match="empty"):
            await service.ingest("Account", BulkOperation.insert, [])
        transport.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_ingest_aborts_job_when_still_abortable_after_failure(self) -> None:
        """Abort is issued when the async ingest job is still abortable at cleanup."""
        transport = MockAsyncTransport()
        transport.send = AsyncMock(
            side_effect=[
                # create_ingest_job
                Response(status_code=200, content=_job_payload(state="Open")),
                # upload_records
                Response(status_code=201, content=b""),
                # close_job raises
                RuntimeError("close failed"),
                # cleanup: get_job -> still Open (abortable)
                Response(status_code=200, content=_job_payload(state="Open")),
                # abort_job
                Response(status_code=200, content=_job_payload(state="Aborted")),
            ]
        )
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        service = AsyncSalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.asyncio.sleep"):
            with pytest.raises(RuntimeError):
                await service.ingest(
                    "Account", BulkOperation.insert, [{"Name": "Acme"}]
                )

        assert transport.send.call_count == 5

    @pytest.mark.asyncio
    async def test_ingest_silences_cleanup_error_and_reraises_original(self) -> None:
        """When get_job raises during async ingest cleanup, original is re-raised."""
        transport = MockAsyncTransport()
        transport.send = AsyncMock(
            side_effect=[
                # create_ingest_job
                Response(status_code=200, content=_job_payload(state="Open")),
                # upload_records raises original error
                RuntimeError("original error"),
                # cleanup: get_job also raises
                RuntimeError("cleanup error"),
            ]
        )
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        service = AsyncSalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.asyncio.sleep"):
            with pytest.raises(RuntimeError, match="original error"):
                await service.ingest(
                    "Account", BulkOperation.insert, [{"Name": "Acme"}]
                )

    # ------------------------------------------------------------------
    # query
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_query_aborts_job_when_still_abortable_after_failure(self) -> None:
        """Abort is issued when the async query job is still abortable at cleanup."""
        transport = MockAsyncTransport()
        transport.send = AsyncMock(
            side_effect=[
                # create_query_job
                Response(
                    status_code=200,
                    content=_job_payload(state="InProgress", operation="query"),
                ),
                # wait_for_job raises
                RuntimeError("poll failed"),
                # cleanup: get_job -> still InProgress (abortable)
                Response(
                    status_code=200,
                    content=_job_payload(state="InProgress", operation="query"),
                ),
                # abort_job
                Response(
                    status_code=200,
                    content=_job_payload(state="Aborted", operation="query"),
                ),
            ]
        )
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        service = AsyncSalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.asyncio.sleep"):
            with pytest.raises(RuntimeError):
                await service.query("SELECT Id FROM Account")

        assert transport.send.call_count == 4

    @pytest.mark.asyncio
    async def test_query_silences_cleanup_error_and_reraises_original(self) -> None:
        """When get_job raises during async query cleanup, original is re-raised."""
        transport = MockAsyncTransport()
        transport.send = AsyncMock(
            side_effect=[
                # create_query_job
                Response(
                    status_code=200,
                    content=_job_payload(state="InProgress", operation="query"),
                ),
                # wait_for_job raises original error
                RuntimeError("original error"),
                # cleanup: get_job also raises
                RuntimeError("cleanup error"),
            ]
        )
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        service = AsyncSalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.asyncio.sleep"):
            with pytest.raises(RuntimeError, match="original error"):
                await service.query("SELECT Id FROM Account")

    @pytest.mark.asyncio
    async def test_query_full_lifecycle(self) -> None:
        """A successful async query runs all lifecycle steps and returns records."""
        csv_content = "Id,Name\nAAA,Acme\n"
        transport = MockAsyncTransport()
        transport.send = AsyncMock(
            side_effect=[
                Response(
                    status_code=200,
                    content=_job_payload(state="InProgress", operation="query"),
                ),
                Response(
                    status_code=200,
                    content=_job_payload(state="JobComplete", operation="query"),
                ),
                Response(status_code=200, content=csv_content.encode(), headers={}),
            ]
        )
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        service = AsyncSalesforceBulkService(client, api_version=API_VERSION)

        with patch("plynth.connectors.salesforce.bulk.service.asyncio.sleep"):
            records = await service.query("SELECT Id, Name FROM Account")

        assert records == [{"Id": "AAA", "Name": "Acme"}]

    # ------------------------------------------------------------------
    # get_query_results
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_query_results_multi_page_pagination(self) -> None:
        """Pages are fetched until Sforce-Locator is absent."""
        page1 = "Id,Name\nAAA,Acme\n"
        page2 = "Id,Name\nBBB,Globex\n"

        transport = MockAsyncTransport()
        transport.send = AsyncMock(
            side_effect=[
                Response(
                    status_code=200,
                    content=page1.encode(),
                    headers={"Sforce-Locator": "tok1"},
                ),
                Response(
                    status_code=200,
                    content=page2.encode(),
                    headers={"Sforce-Locator": "null"},
                ),
            ]
        )
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        service = AsyncSalesforceBulkService(client, api_version=API_VERSION)

        records = await service.get_query_results(JOB_ID)
        assert len(records) == 2
        assert records[1]["Name"] == "Globex"


# ---------------------------------------------------------------------------
# Facade integration
# ---------------------------------------------------------------------------


class TestSalesforceAPIFacade:
    """Tests that the facade exposes bulk() factory methods."""

    def test_bulk_returns_bulk_service(self) -> None:
        """SalesforceAPIFacade.bulk() returns SalesforceBulkService."""
        transport = MockSyncTransport()
        client = APIClient(base_url=BASE_URL, transport=transport)
        facade = SalesforceAPIFacade(client)
        service = facade.bulk()
        assert isinstance(service, SalesforceBulkService)

    def test_bulk_accepts_custom_api_version(self) -> None:
        """Passing api_version propagates to the returned service."""
        transport = MockSyncTransport()
        client = APIClient(base_url=BASE_URL, transport=transport)
        facade = SalesforceAPIFacade(client)
        service = facade.bulk(api_version="59.0")
        assert service._api_version == "59.0"


class TestAsyncSalesforceAPIFacade:
    """Tests that the async facade exposes bulk() factory methods."""

    def test_bulk_returns_async_bulk_service(self) -> None:
        """AsyncSalesforceAPIFacade.bulk() returns AsyncSalesforceBulkService."""
        transport = MockAsyncTransport()
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        facade = AsyncSalesforceAPIFacade(client)
        service = facade.bulk()
        assert isinstance(service, AsyncSalesforceBulkService)

    def test_bulk_defaults_api_version_to_none(self) -> None:
        """Async facade bulk factory keeps api_version unset by default."""
        transport = MockAsyncTransport()
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        facade = AsyncSalesforceAPIFacade(client)

        service = facade.bulk()

        assert service._api_version is None
