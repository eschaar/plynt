"""Salesforce Bulk API 2.0 service.

Provides sync and async services for large-scale Salesforce data operations
via the Bulk API 2.0 job lifecycle: create → upload → close → poll → retrieve.

Two job types are supported:

- **Ingest**: insert, update, upsert, delete, or hard_delete records in bulk.
- **Query**: extract large result sets via SOQL, returned as ``list[dict]``.

The high-level ``ingest()`` and ``query()`` helpers manage the full lifecycle
internally, including cleanup on failure. Low-level primitives are available
for callers that need direct control over individual lifecycle steps.

Salesforce API constraints enforced by this module (see ADR SF-0005):

- Upload payloads exceeding 100 MB raise ``ValueError`` before the request.
- ``upsert`` without ``external_id_field`` raises ``ValueError``.
- Job-level failures raise ``SalesforceBulkJobError``.
- Polling timeout raises ``BulkJobTimeoutError``.

Example — ingest::

    bulk = facade.bulk()
    result = bulk.ingest(
        "Account",
        BulkOperation.insert,
        [{"Name": "Acme Corp"}, {"Name": "Globex"}],
    )
    print(f"OK: {len(result.successful)}, failed: {len(result.failed)}")

Example — query::

    bulk = facade.bulk()
    records = bulk.query("SELECT Id, Name FROM Account LIMIT 1000")
    for record in records:
        print(record["Name"])

"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import math
import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from plynth.connectors.salesforce.constants import (
    resolve_async_api_version,
    resolve_sync_api_version,
)
from plynth.connectors.salesforce.errors import (
    BulkJobTimeoutError,
    SalesforceBulkJobError,
)
from plynth.connectors.salesforce.renderer import SalesforceRenderer
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import Renderer
from plynth.http.service import APIService, AsyncAPIService

__all__ = [
    "AsyncSalesforceBulkService",
    "BulkIngestResult",
    "BulkJobInfo",
    "BulkJobState",
    "BulkOperation",
    "SalesforceBulkService",
]

_CSV_CONTENT_TYPE = "text/csv; charset=UTF-8"
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB per Salesforce Bulk API 2.0 limit
_POLL_INITIAL = 0.5  # seconds — initial backoff interval
_POLL_MAX_INTERVAL = 2.0  # seconds — maximum backoff interval cap


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BulkOperation(StrEnum):
    """Salesforce Bulk API 2.0 operation types."""

    insert = "insert"
    update = "update"
    upsert = "upsert"
    delete = "delete"
    hard_delete = "hardDelete"
    query = "query"
    query_all = "queryAll"


class BulkJobState(StrEnum):
    """Salesforce Bulk API 2.0 job lifecycle states.

    Ingest state machine::

        Open → UploadComplete → InProgress → JobComplete
                                            ↘ Failed
                             ↘ Aborted (from Open or UploadComplete)

    Query jobs skip directly to ``InProgress``; there is no upload phase.

    """

    open = "Open"
    upload_complete = "UploadComplete"
    in_progress = "InProgress"
    job_complete = "JobComplete"
    aborted = "Aborted"
    failed = "Failed"


_TERMINAL_STATES: frozenset[BulkJobState] = frozenset(
    {BulkJobState.job_complete, BulkJobState.aborted, BulkJobState.failed}
)

_ABORTABLE_STATES: frozenset[BulkJobState] = frozenset(
    {BulkJobState.open, BulkJobState.upload_complete, BulkJobState.in_progress}
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class BulkJobInfo(BaseModel):
    """Salesforce Bulk API 2.0 job metadata.

    Returned by job creation, status, close, and abort endpoints. Fields
    related to processing statistics (``number_records_processed`` etc.) are
    only populated after the job reaches a terminal state.

    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    operation: str
    sobject: str = Field(alias="object")
    state: BulkJobState
    content_url: str | None = Field(None, alias="contentUrl")
    api_version: float | None = Field(None, alias="apiVersion")
    created_date: str | None = Field(None, alias="createdDate")
    column_delimiter: str | None = Field(None, alias="columnDelimiter")
    line_ending: str | None = Field(None, alias="lineEnding")
    number_records_processed: int | None = Field(None, alias="numberRecordsProcessed")
    number_records_failed: int | None = Field(None, alias="numberRecordsFailed")
    total_processing_time: int | None = Field(None, alias="totalProcessingTime")
    error_message: str | None = Field(None, alias="errorMessage")


class BulkIngestResult(BaseModel):
    """Aggregated results for a completed Bulk API 2.0 ingest job.

    Attributes:
        successful: Records processed successfully; each dict includes
            ``sf__Id`` and ``sf__Created`` alongside the original fields.
        failed: Records that failed; each dict includes ``sf__Id`` and
            ``sf__Error`` alongside the original fields.
        unprocessed: Records not processed (job aborted or failed early).

    """

    successful: list[dict[str, Any]] = Field(default_factory=list)
    failed: list[dict[str, Any]] = Field(default_factory=list)
    unprocessed: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Private CSV helpers
# ---------------------------------------------------------------------------


def _records_to_csv(records: list[dict[str, Any]]) -> bytes:
    """Serialise a list of dicts to UTF-8 CSV bytes."""
    if not records:
        return b""
    keys: list[str] = list(dict.fromkeys(k for r in records for k in r))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore", restval="")
    writer.writeheader()
    writer.writerows(records)
    return buf.getvalue().encode("utf-8")


def _csv_to_records(csv_text: str) -> list[dict[str, Any]]:
    r"""Deserialise a CSV string to a list of dicts, stripping embedded null bytes."""
    cleaned = csv_text.replace("\x00", "")
    if not cleaned.strip():
        return []
    return [dict(row) for row in csv.DictReader(io.StringIO(cleaned))]


def _poll_delay(attempt: int) -> float:
    """Return the exponential backoff delay for a polling attempt."""
    return min(_POLL_MAX_INTERVAL, _POLL_INITIAL * math.pow(2, attempt))


# ---------------------------------------------------------------------------
# Sync service
# ---------------------------------------------------------------------------


class SalesforceBulkService(APIService):
    """Service for Salesforce Bulk API 2.0 ingest and query jobs.

    Provides high-level ``ingest()`` and ``query()`` helpers that manage the
    full job lifecycle, and low-level primitives for callers that need direct
    control over individual lifecycle steps.

    Example::

        bulk = facade.bulk()
        result = bulk.ingest(
            "Account",
            BulkOperation.insert,
            [{"Name": "Acme Corp"}],
        )

    """

    def __init__(
        self,
        client: APIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize SalesforceBulkService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = resolve_sync_api_version(client, api_version)

    # -- Path helpers --------------------------------------------------------

    def _ingest_path(self, job_id: str | None = None, suffix: str | None = None) -> str:
        """Return the Bulk API 2.0 ingest jobs endpoint path."""
        base = f"/services/data/v{self._api_version}/jobs/ingest"
        if job_id:
            base = f"{base}/{job_id}"
        if suffix:
            base = f"{base}/{suffix}"
        return base

    def _query_path(self, job_id: str | None = None, suffix: str | None = None) -> str:
        """Return the Bulk API 2.0 query jobs endpoint path."""
        base = f"/services/data/v{self._api_version}/jobs/query"
        if job_id:
            base = f"{base}/{job_id}"
        if suffix:
            base = f"{base}/{suffix}"
        return base

    # -- Low-level primitives ------------------------------------------------

    def create_ingest_job(
        self,
        sobject: str,
        operation: BulkOperation,
        *,
        external_id_field: str | None = None,
    ) -> BulkJobInfo:
        """Create a Bulk API 2.0 ingest job.

        Args:
            sobject: Salesforce object API name, e.g. ``"Account"``.
            external_id_field: Required when ``operation`` is ``upsert``; the
                external ID field API name used for matching.

        Raises:
            ValueError: If ``operation`` is ``upsert`` and ``external_id_field``
                is not provided.

        """
        if operation == BulkOperation.upsert and not external_id_field:
            raise ValueError("external_id_field is required for upsert operations")
        payload: dict[str, Any] = {
            "operation": operation,
            "object": sobject,
            "contentType": "CSV",
        }
        if external_id_field:
            payload["externalIdFieldName"] = external_id_field
        resp = self._client.post(
            self._ingest_path(),
            content=json.dumps(payload).encode(),
        )
        return BulkJobInfo.model_validate_json(resp.content)

    def create_query_job(
        self,
        soql: str,
        *,
        include_deleted: bool = False,
    ) -> BulkJobInfo:
        """Create a Bulk API 2.0 query job.

        Args:
            include_deleted: When ``True``, uses ``queryAll`` to include
                soft-deleted and archived records.

        """
        operation = BulkOperation.query_all if include_deleted else BulkOperation.query
        payload: dict[str, Any] = {"operation": operation, "query": soql}
        resp = self._client.post(
            self._query_path(),
            content=json.dumps(payload).encode(),
        )
        return BulkJobInfo.model_validate_json(resp.content)

    def get_job(self, job_id: str, *, is_query: bool) -> BulkJobInfo:
        """Retrieve the current status and metadata of a bulk job."""
        path = self._query_path(job_id) if is_query else self._ingest_path(job_id)
        resp = self._client.get(path)
        return BulkJobInfo.model_validate_json(resp.content)

    def upload_records(
        self,
        job_id: str,
        records: list[dict[str, Any]],
        *,
        content_url: str | None = None,
    ) -> None:
        """Upload records to an open ingest job as CSV.

        Args:
            records: Records to upload; each dict maps field API names to values.
            content_url: Upload URL from the job creation response
                (``BulkJobInfo.content_url``). Constructed from ``job_id``
                when not provided.

        Raises:
            ValueError: If ``records`` is empty or the serialised CSV exceeds
                the 100 MB Salesforce limit.

        """
        if not records:
            raise ValueError("records must not be empty")
        csv_data = _records_to_csv(records)
        if len(csv_data) > _MAX_UPLOAD_BYTES:
            raise ValueError(
                f"Serialised CSV size {len(csv_data):,} bytes exceeds the "
                "100 MB Salesforce Bulk API 2.0 upload limit"
            )
        path = content_url or self._ingest_path(job_id, "batches")
        self._client.put(
            path,
            content=csv_data,
            headers={"Content-Type": _CSV_CONTENT_TYPE},
        )

    def close_job(self, job_id: str) -> BulkJobInfo:
        """Close an ingest job, signalling that all data has been uploaded."""
        resp = self._client.patch(
            self._ingest_path(job_id),
            content=json.dumps({"state": "UploadComplete"}).encode(),
        )
        return BulkJobInfo.model_validate_json(resp.content)

    def abort_job(self, job_id: str, *, is_query: bool) -> BulkJobInfo:
        """Abort an active bulk job."""
        path = self._query_path(job_id) if is_query else self._ingest_path(job_id)
        resp = self._client.patch(
            path,
            content=json.dumps({"state": "Aborted"}).encode(),
        )
        return BulkJobInfo.model_validate_json(resp.content)

    def delete_job(self, job_id: str, *, is_query: bool) -> None:
        """Delete a bulk job and its associated data."""
        path = self._query_path(job_id) if is_query else self._ingest_path(job_id)
        self._client.delete(path)

    def wait_for_job(
        self,
        job_id: str,
        *,
        is_query: bool,
        max_wait: float | None = None,
    ) -> BulkJobInfo:
        """Poll a bulk job until it reaches a terminal state.

        Uses exponential backoff starting at 0.5 s, capped at 2 s, which
        balances responsiveness for short jobs with API courtesy for long ones.

        Args:
            is_query: ``True`` for query jobs, ``False`` for ingest jobs.
            max_wait: Maximum total wait time in seconds. Waits indefinitely
                when ``None``.

        Raises:
            SalesforceBulkJobError: If the job ends in ``Aborted`` or
                ``Failed`` state.
            BulkJobTimeoutError: If ``max_wait`` is exceeded before the job
                reaches a terminal state.

        """
        deadline = time.monotonic() + max_wait if max_wait is not None else None
        attempt = 0
        while True:
            time.sleep(_poll_delay(attempt))
            attempt += 1
            job = self.get_job(job_id, is_query=is_query)
            if job.state in _TERMINAL_STATES:
                if job.state is not BulkJobState.job_complete:
                    msg = job.error_message or f"Job ended in state {job.state!r}"
                    raise SalesforceBulkJobError(job_id=job_id, message=msg)
                return job
            if deadline is not None and time.monotonic() >= deadline:
                raise BulkJobTimeoutError(job_id=job_id, max_wait=max_wait)  # type: ignore[arg-type]

    def get_ingest_results(self, job_id: str) -> BulkIngestResult:
        """Retrieve the results of a completed ingest job."""

        def _fetch(suffix: str) -> list[dict[str, Any]]:
            """Fetch and parse a single ingest result CSV from the given URL suffix."""
            resp = self._client.get(
                self._ingest_path(job_id, suffix),
                headers={"Accept": _CSV_CONTENT_TYPE},
            )
            return _csv_to_records(resp.content.decode("utf-8"))

        return BulkIngestResult(
            successful=_fetch("successfulResults"),
            failed=_fetch("failedResults"),
            unprocessed=_fetch("unprocessedrecords"),
        )

    def get_query_results(self, job_id: str) -> list[dict[str, Any]]:
        """Retrieve all results for a completed query job, auto-paginating.

        Follows ``Sforce-Locator`` pagination until all pages are consumed.

        """
        all_records: list[dict[str, Any]] = []
        locator = ""
        while True:
            params: dict[str, Any] = {}
            if locator:
                params["locator"] = locator
            resp = self._client.get(
                self._query_path(job_id, "results"),
                params=params,
                headers={"Accept": _CSV_CONTENT_TYPE},
            )
            all_records.extend(_csv_to_records(resp.content.decode("utf-8")))
            locator = resp.headers.get("Sforce-Locator", "")
            if not locator or locator == "null":
                break
        return all_records

    # -- High-level helpers --------------------------------------------------

    def ingest(
        self,
        sobject: str,
        operation: BulkOperation,
        records: list[dict[str, Any]],
        *,
        external_id_field: str | None = None,
        max_wait: float | None = None,
    ) -> BulkIngestResult:
        """Run a complete Bulk API 2.0 ingest job and return the results.

        Manages the full lifecycle: create → upload → close → poll → retrieve.
        Aborts the job automatically if any step raises an exception.

        Args:
            sobject: Salesforce object API name, e.g. ``"Account"``.
            records: Records to process; each dict maps field API names to values.
            external_id_field: Required when ``operation`` is ``upsert``.
            max_wait: Maximum polling time in seconds; waits indefinitely when
                ``None``.

        Raises:
            ValueError: If ``records`` is empty, ``operation`` is ``upsert``
                without ``external_id_field``, or the payload exceeds 100 MB.
            SalesforceBulkJobError: If the job ends in a failed or aborted state.
            BulkJobTimeoutError: If ``max_wait`` is exceeded during polling.

        Example::

            result = bulk.ingest(
                "Contact",
                BulkOperation.upsert,
                [{"UserName__c": "ada-001", "FirstName": "Ada"}],
                external_id_field="UserName__c",
            )

        """
        if not records:
            raise ValueError("records must not be empty")
        job = self.create_ingest_job(
            sobject, operation, external_id_field=external_id_field
        )
        try:
            self.upload_records(job.id, records, content_url=job.content_url)
            self.close_job(job.id)
            self.wait_for_job(job.id, is_query=False, max_wait=max_wait)
            return self.get_ingest_results(job.id)
        except Exception:
            try:
                current = self.get_job(job.id, is_query=False)
                if current.state in _ABORTABLE_STATES:
                    self.abort_job(job.id, is_query=False)
            except Exception:  # noqa: S110
                pass
            raise

    def query(
        self,
        soql: str,
        *,
        include_deleted: bool = False,
        max_wait: float | None = None,
    ) -> list[dict[str, Any]]:
        """Run a complete Bulk API 2.0 query job and return all records.

        Manages the full lifecycle: create → poll → retrieve (auto-paginated).
        Aborts the job automatically if any step raises an exception.

        Args:
            include_deleted: When ``True``, uses ``queryAll`` to include
                soft-deleted and archived records.
            max_wait: Maximum polling time in seconds; waits indefinitely when
                ``None``.

        Raises:
            SalesforceBulkJobError: If the job ends in a failed or aborted state.
            BulkJobTimeoutError: If ``max_wait`` is exceeded during polling.

        Example::

            records = bulk.query("SELECT Id, Name FROM Account LIMIT 10000")

        """
        job = self.create_query_job(soql, include_deleted=include_deleted)
        try:
            self.wait_for_job(job.id, is_query=True, max_wait=max_wait)
            return self.get_query_results(job.id)
        except Exception:
            try:
                current = self.get_job(job.id, is_query=True)
                if current.state in _ABORTABLE_STATES:
                    self.abort_job(job.id, is_query=True)
            except Exception:  # noqa: S110
                pass
            raise


# ---------------------------------------------------------------------------
# Async service
# ---------------------------------------------------------------------------


class AsyncSalesforceBulkService(AsyncAPIService):
    """Async service for Salesforce Bulk API 2.0 ingest and query jobs.

    Async counterpart of ``SalesforceBulkService`` — all endpoint methods are
    ``async def`` and require an ``AsyncAPIClient``. The API surface is
    structurally identical to the sync variant.

    Example::

        bulk = async_facade.bulk()
        result = await bulk.ingest(
            "Account",
            BulkOperation.insert,
            [{"Name": "Acme Corp"}],
        )

    """

    def __init__(
        self,
        client: AsyncAPIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncSalesforceBulkService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = api_version

    # -- Path helpers --------------------------------------------------------

    async def _ingest_path(
        self, job_id: str | None = None, suffix: str | None = None
    ) -> str:
        """Return the Bulk API 2.0 ingest jobs endpoint path."""
        if self._api_version is None:
            self._api_version = await resolve_async_api_version(
                self._client,
                self._api_version,
            )
        base = f"/services/data/v{self._api_version}/jobs/ingest"
        if job_id:
            base = f"{base}/{job_id}"
        if suffix:
            base = f"{base}/{suffix}"
        return base

    async def _query_path(
        self, job_id: str | None = None, suffix: str | None = None
    ) -> str:
        """Return the Bulk API 2.0 query jobs endpoint path."""
        if self._api_version is None:
            self._api_version = await resolve_async_api_version(
                self._client,
                self._api_version,
            )
        base = f"/services/data/v{self._api_version}/jobs/query"
        if job_id:
            base = f"{base}/{job_id}"
        if suffix:
            base = f"{base}/{suffix}"
        return base

    # -- Low-level primitives ------------------------------------------------

    async def create_ingest_job(
        self,
        sobject: str,
        operation: BulkOperation,
        *,
        external_id_field: str | None = None,
    ) -> BulkJobInfo:
        """Create a Bulk API 2.0 ingest job.

        Args:
            sobject: Salesforce object API name, e.g. ``"Account"``.
            external_id_field: Required when ``operation`` is ``upsert``; the
                external ID field API name used for matching.

        Raises:
            ValueError: If ``operation`` is ``upsert`` and ``external_id_field``
                is not provided.

        """
        if operation == BulkOperation.upsert and not external_id_field:
            raise ValueError("external_id_field is required for upsert operations")
        payload: dict[str, Any] = {
            "operation": operation,
            "object": sobject,
            "contentType": "CSV",
        }
        if external_id_field:
            payload["externalIdFieldName"] = external_id_field
        resp = await self._client.post(
            await self._ingest_path(),
            content=json.dumps(payload).encode(),
        )
        return BulkJobInfo.model_validate_json(resp.content)

    async def create_query_job(
        self,
        soql: str,
        *,
        include_deleted: bool = False,
    ) -> BulkJobInfo:
        """Create a Bulk API 2.0 query job.

        Args:
            include_deleted: When ``True``, uses ``queryAll`` to include
                soft-deleted and archived records.

        """
        operation = BulkOperation.query_all if include_deleted else BulkOperation.query
        payload: dict[str, Any] = {"operation": operation, "query": soql}
        resp = await self._client.post(
            await self._query_path(),
            content=json.dumps(payload).encode(),
        )
        return BulkJobInfo.model_validate_json(resp.content)

    async def get_job(self, job_id: str, *, is_query: bool) -> BulkJobInfo:
        """Retrieve the current status and metadata of a bulk job."""
        path = (
            await self._query_path(job_id)
            if is_query
            else await self._ingest_path(job_id)
        )
        resp = await self._client.get(path)
        return BulkJobInfo.model_validate_json(resp.content)

    async def upload_records(
        self,
        job_id: str,
        records: list[dict[str, Any]],
        *,
        content_url: str | None = None,
    ) -> None:
        """Upload records to an open ingest job as CSV.

        Args:
            records: Records to upload; each dict maps field API names to values.
            content_url: Upload URL from the job creation response
                (``BulkJobInfo.content_url``). Constructed from ``job_id``
                when not provided.

        Raises:
            ValueError: If ``records`` is empty or the serialised CSV exceeds
                the 100 MB Salesforce limit.

        """
        if not records:
            raise ValueError("records must not be empty")
        csv_data = _records_to_csv(records)
        if len(csv_data) > _MAX_UPLOAD_BYTES:
            raise ValueError(
                f"Serialised CSV size {len(csv_data):,} bytes exceeds the "
                "100 MB Salesforce Bulk API 2.0 upload limit"
            )
        path = content_url or await self._ingest_path(job_id, "batches")
        await self._client.put(
            path,
            content=csv_data,
            headers={"Content-Type": _CSV_CONTENT_TYPE},
        )

    async def close_job(self, job_id: str) -> BulkJobInfo:
        """Close an ingest job, signalling that all data has been uploaded."""
        resp = await self._client.patch(
            await self._ingest_path(job_id),
            content=json.dumps({"state": "UploadComplete"}).encode(),
        )
        return BulkJobInfo.model_validate_json(resp.content)

    async def abort_job(self, job_id: str, *, is_query: bool) -> BulkJobInfo:
        """Abort an active bulk job."""
        path = (
            await self._query_path(job_id)
            if is_query
            else await self._ingest_path(job_id)
        )
        resp = await self._client.patch(
            path,
            content=json.dumps({"state": "Aborted"}).encode(),
        )
        return BulkJobInfo.model_validate_json(resp.content)

    async def delete_job(self, job_id: str, *, is_query: bool) -> None:
        """Delete a bulk job and its associated data."""
        path = (
            await self._query_path(job_id)
            if is_query
            else await self._ingest_path(job_id)
        )
        await self._client.delete(path)

    async def wait_for_job(
        self,
        job_id: str,
        *,
        is_query: bool,
        max_wait: float | None = None,
    ) -> BulkJobInfo:
        """Poll a bulk job until it reaches a terminal state.

        Uses exponential backoff starting at 0.5 s, capped at 2 s, which
        balances responsiveness for short jobs with API courtesy for long ones.

        Args:
            is_query: ``True`` for query jobs, ``False`` for ingest jobs.
            max_wait: Maximum total wait time in seconds. Waits indefinitely
                when ``None``.

        Raises:
            SalesforceBulkJobError: If the job ends in ``Aborted`` or
                ``Failed`` state.
            BulkJobTimeoutError: If ``max_wait`` is exceeded before the job
                reaches a terminal state.

        """
        deadline = time.monotonic() + max_wait if max_wait is not None else None
        attempt = 0
        while True:
            await asyncio.sleep(_poll_delay(attempt))
            attempt += 1
            job = await self.get_job(job_id, is_query=is_query)
            if job.state in _TERMINAL_STATES:
                if job.state is not BulkJobState.job_complete:
                    msg = job.error_message or f"Job ended in state {job.state!r}"
                    raise SalesforceBulkJobError(job_id=job_id, message=msg)
                return job
            if deadline is not None and time.monotonic() >= deadline:
                raise BulkJobTimeoutError(job_id=job_id, max_wait=max_wait)  # type: ignore[arg-type]

    async def get_ingest_results(self, job_id: str) -> BulkIngestResult:
        """Retrieve the results of a completed ingest job."""

        async def _fetch(suffix: str) -> list[dict[str, Any]]:
            """Fetch and parse a single ingest result CSV from the given URL suffix."""
            resp = await self._client.get(
                await self._ingest_path(job_id, suffix),
                headers={"Accept": _CSV_CONTENT_TYPE},
            )
            return _csv_to_records(resp.content.decode("utf-8"))

        return BulkIngestResult(
            successful=await _fetch("successfulResults"),
            failed=await _fetch("failedResults"),
            unprocessed=await _fetch("unprocessedrecords"),
        )

    async def get_query_results(self, job_id: str) -> list[dict[str, Any]]:
        """Retrieve all results for a completed query job, auto-paginating.

        Follows ``Sforce-Locator`` pagination until all pages are consumed.

        """
        all_records: list[dict[str, Any]] = []
        locator = ""
        while True:
            params: dict[str, Any] = {}
            if locator:
                params["locator"] = locator
            resp = await self._client.get(
                await self._query_path(job_id, "results"),
                params=params,
                headers={"Accept": _CSV_CONTENT_TYPE},
            )
            all_records.extend(_csv_to_records(resp.content.decode("utf-8")))
            locator = resp.headers.get("Sforce-Locator", "")
            if not locator or locator == "null":
                break
        return all_records

    # -- High-level helpers --------------------------------------------------

    async def ingest(
        self,
        sobject: str,
        operation: BulkOperation,
        records: list[dict[str, Any]],
        *,
        external_id_field: str | None = None,
        max_wait: float | None = None,
    ) -> BulkIngestResult:
        """Run a complete Bulk API 2.0 ingest job and return the results.

        Manages the full lifecycle: create → upload → close → poll → retrieve.
        Aborts the job automatically if any step raises an exception.

        Args:
            sobject: Salesforce object API name, e.g. ``"Account"``.
            records: Records to process; each dict maps field API names to values.
            external_id_field: Required when ``operation`` is ``upsert``.
            max_wait: Maximum polling time in seconds; waits indefinitely when
                ``None``.

        Raises:
            ValueError: If ``records`` is empty, ``operation`` is ``upsert``
                without ``external_id_field``, or the payload exceeds 100 MB.
            SalesforceBulkJobError: If the job ends in a failed or aborted state.
            BulkJobTimeoutError: If ``max_wait`` is exceeded during polling.

        Example::

            result = await bulk.ingest(
                "Contact",
                BulkOperation.upsert,
                [{"UserName__c": "ada-001", "FirstName": "Ada"}],
                external_id_field="UserName__c",
            )

        """
        if not records:
            raise ValueError("records must not be empty")
        job = await self.create_ingest_job(
            sobject, operation, external_id_field=external_id_field
        )
        try:
            await self.upload_records(job.id, records, content_url=job.content_url)
            await self.close_job(job.id)
            await self.wait_for_job(job.id, is_query=False, max_wait=max_wait)
            return await self.get_ingest_results(job.id)
        except Exception:
            try:
                current = await self.get_job(job.id, is_query=False)
                if current.state in _ABORTABLE_STATES:
                    await self.abort_job(job.id, is_query=False)
            except Exception:  # noqa: S110
                pass
            raise

    async def query(
        self,
        soql: str,
        *,
        include_deleted: bool = False,
        max_wait: float | None = None,
    ) -> list[dict[str, Any]]:
        """Run a complete Bulk API 2.0 query job and return all records.

        Manages the full lifecycle: create → poll → retrieve (auto-paginated).
        Aborts the job automatically if any step raises an exception.

        Args:
            include_deleted: When ``True``, uses ``queryAll`` to include
                soft-deleted and archived records.
            max_wait: Maximum polling time in seconds; waits indefinitely when
                ``None``.

        Raises:
            SalesforceBulkJobError: If the job ends in a failed or aborted state.
            BulkJobTimeoutError: If ``max_wait`` is exceeded during polling.

        Example::

            records = await bulk.query("SELECT Id, Name FROM Account LIMIT 10000")

        """
        job = await self.create_query_job(soql, include_deleted=include_deleted)
        try:
            await self.wait_for_job(job.id, is_query=True, max_wait=max_wait)
            return await self.get_query_results(job.id)
        except Exception:
            try:
                current = await self.get_job(job.id, is_query=True)
                if current.state in _ABORTABLE_STATES:
                    await self.abort_job(job.id, is_query=True)
            except Exception:  # noqa: S110
                pass
            raise
