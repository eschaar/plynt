"""Salesforce composite REST service building blocks.

Provides typed request and response models plus sync and async services for
the generic Salesforce composite endpoints:

- ``/composite`` for chained REST subrequests
- ``/composite/batch`` for grouped REST requests
- ``/composite/tree`` for hierarchical create flows

The service methods are intentionally generic: they expose the Salesforce REST
primitives without embedding business workflows or org-specific orchestration.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from plynt.connectors.salesforce.constants import (
    resolve_async_api_version,
    resolve_sync_api_version,
)
from plynt.connectors.salesforce.models import SObjectError
from plynt.connectors.salesforce.renderer import SalesforceRenderer
from plynt.http.client import APIClient, AsyncAPIClient
from plynt.http.renderer import Renderer
from plynt.http.service import APIService, AsyncAPIService

__all__ = [
    "AsyncSalesforceCompositeService",
    "CompositeBatchRequest",
    "CompositeBatchResponse",
    "CompositeBatchResult",
    "CompositeBatchSubrequest",
    "CompositeRequest",
    "CompositeResponse",
    "CompositeSubrequest",
    "CompositeSubrequestResponse",
    "CompositeTreeRecordResult",
    "CompositeTreeRequest",
    "CompositeTreeResponse",
    "SalesforceCompositeService",
]


class CompositeSubrequest(BaseModel):
    """A single subrequest in a Salesforce composite request."""

    model_config = ConfigDict(populate_by_name=True)

    method: str
    url: str
    reference_id: str = Field(alias="referenceId")
    body: dict[str, Any] | list[Any] | str | int | float | bool | None = None
    http_headers: dict[str, str] | None = Field(None, alias="httpHeaders")


class CompositeRequest(BaseModel):
    """Envelope for the ``/composite`` endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    composite_request: list[CompositeSubrequest] = Field(alias="compositeRequest")
    all_or_none: bool = Field(False, alias="allOrNone")
    collate_subrequests: bool = Field(False, alias="collateSubrequests")


class CompositeSubrequestResponse(BaseModel):
    """Single response entry from the ``/composite`` endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    http_status_code: int = Field(alias="httpStatusCode")
    reference_id: str = Field(alias="referenceId")
    body: dict[str, Any] | list[Any] | str | int | float | bool | None = None


class CompositeResponse(BaseModel):
    """Typed response for the ``/composite`` endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    composite_response: list[CompositeSubrequestResponse] = Field(
        alias="compositeResponse"
    )
    has_errors: bool = Field(alias="hasErrors")


class CompositeBatchSubrequest(BaseModel):
    """A single subrequest in a Salesforce composite batch request."""

    model_config = ConfigDict(populate_by_name=True)

    method: str
    url: str
    reference_id: str | None = Field(None, alias="referenceId")
    rich_input: dict[str, Any] | list[Any] | str | int | float | bool | None = Field(
        None,
        alias="richInput",
    )
    http_headers: dict[str, str] | None = Field(None, alias="httpHeaders")


class CompositeBatchRequest(BaseModel):
    """Envelope for the ``/composite/batch`` endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    batch_requests: list[CompositeBatchSubrequest] = Field(alias="batchRequests")
    halt_on_error: bool = Field(False, alias="haltOnError")


class CompositeBatchResult(BaseModel):
    """Single result entry from the ``/composite/batch`` endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    status_code: int = Field(alias="statusCode")
    result: dict[str, Any] | list[Any] | str | int | float | bool | None = None
    reference_id: str | None = Field(None, alias="referenceId")


class CompositeBatchResponse(BaseModel):
    """Typed response for the ``/composite/batch`` endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    has_errors: bool = Field(alias="hasErrors")
    results: list[CompositeBatchResult]


class CompositeTreeRequest(BaseModel):
    """Envelope for the ``/composite/tree`` endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    all_or_none: bool = Field(False, alias="allOrNone")
    records: list[dict[str, Any]]


class CompositeTreeRecordResult(BaseModel):
    """Single result entry from the ``/composite/tree`` endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    reference_id: str = Field(alias="referenceId")
    id: str
    errors: list[SObjectError] = Field(default_factory=list)


class CompositeTreeResponse(BaseModel):
    """Typed response for the ``/composite/tree`` endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    has_errors: bool = Field(alias="hasErrors")
    results: list[CompositeTreeRecordResult]


def _render_payload(renderer: Renderer, payload: BaseModel) -> bytes:
    """Render a Pydantic model as Salesforce JSON bytes."""
    return renderer.render(payload.model_dump(by_alias=True, exclude_none=True))


def _coerce_composite_subrequest(
    request: CompositeSubrequest | dict[str, Any],
) -> CompositeSubrequest:
    """Coerce a composite subrequest from a model or raw dict."""
    if isinstance(request, CompositeSubrequest):
        return request
    return CompositeSubrequest.model_validate(request)


def _coerce_batch_subrequest(
    request: CompositeBatchSubrequest | dict[str, Any],
) -> CompositeBatchSubrequest:
    """Coerce a batch subrequest from a model or raw dict."""
    if isinstance(request, CompositeBatchSubrequest):
        return request
    return CompositeBatchSubrequest.model_validate(request)


def _dump_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a shallow copy of tree records for rendering."""
    return [dict(record) for record in records]


class SalesforceCompositeService(APIService):
    """Service for generic Salesforce composite REST endpoints."""

    def __init__(
        self,
        client: APIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize SalesforceCompositeService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = resolve_sync_api_version(client, api_version)

    def _base_path(self) -> str:
        """Return the versioned Salesforce REST API base path."""
        return f"/services/data/v{self._api_version}"

    def composite(
        self,
        requests: list[CompositeSubrequest | dict[str, Any]],
        *,
        all_or_none: bool = False,
        collate_subrequests: bool = False,
    ) -> CompositeResponse:
        """Execute a chained composite request."""
        payload = CompositeRequest.model_validate(
            {
                "compositeRequest": [
                    _coerce_composite_subrequest(req).model_dump(
                        by_alias=True,
                        exclude_none=True,
                    )
                    for req in requests
                ],
                "allOrNone": all_or_none,
                "collateSubrequests": collate_subrequests,
            }
        )
        resp = self._client.post(
            f"{self._base_path()}/composite",
            content=_render_payload(self._renderer, payload),
        )
        return CompositeResponse.model_validate_json(resp.content)

    def batch(
        self,
        requests: list[CompositeBatchSubrequest | dict[str, Any]],
        *,
        halt_on_error: bool = False,
    ) -> CompositeBatchResponse:
        """Execute a composite batch request."""
        payload = CompositeBatchRequest.model_validate(
            {
                "batchRequests": [
                    _coerce_batch_subrequest(req).model_dump(
                        by_alias=True,
                        exclude_none=True,
                    )
                    for req in requests
                ],
                "haltOnError": halt_on_error,
            }
        )
        resp = self._client.post(
            f"{self._base_path()}/composite/batch",
            content=_render_payload(self._renderer, payload),
        )
        return CompositeBatchResponse.model_validate_json(resp.content)

    def tree(
        self,
        object_name: str,
        records: list[dict[str, Any]],
        *,
        all_or_none: bool = False,
    ) -> CompositeTreeResponse:
        """Execute a hierarchical tree create request."""
        payload = CompositeTreeRequest.model_validate(
            {"allOrNone": all_or_none, "records": _dump_records(records)}
        )
        resp = self._client.post(
            f"{self._base_path()}/composite/tree/{object_name}",
            content=_render_payload(self._renderer, payload),
        )
        return CompositeTreeResponse.model_validate_json(resp.content)


class AsyncSalesforceCompositeService(AsyncAPIService):
    """Async service for generic Salesforce composite REST endpoints."""

    def __init__(
        self,
        client: AsyncAPIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncSalesforceCompositeService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = api_version

    async def _base_path(self) -> str:
        """Return the versioned Salesforce REST API base path."""
        if self._api_version is None:
            self._api_version = await resolve_async_api_version(
                self._client,
                self._api_version,
            )
        return f"/services/data/v{self._api_version}"

    async def composite(
        self,
        requests: list[CompositeSubrequest | dict[str, Any]],
        *,
        all_or_none: bool = False,
        collate_subrequests: bool = False,
    ) -> CompositeResponse:
        """Execute a chained composite request."""
        base_path = await self._base_path()
        payload = CompositeRequest.model_validate(
            {
                "compositeRequest": [
                    _coerce_composite_subrequest(req).model_dump(
                        by_alias=True,
                        exclude_none=True,
                    )
                    for req in requests
                ],
                "allOrNone": all_or_none,
                "collateSubrequests": collate_subrequests,
            }
        )
        resp = await self._client.post(
            f"{base_path}/composite",
            content=_render_payload(self._renderer, payload),
        )
        return CompositeResponse.model_validate_json(resp.content)

    async def batch(
        self,
        requests: list[CompositeBatchSubrequest | dict[str, Any]],
        *,
        halt_on_error: bool = False,
    ) -> CompositeBatchResponse:
        """Execute a composite batch request."""
        base_path = await self._base_path()
        payload = CompositeBatchRequest.model_validate(
            {
                "batchRequests": [
                    _coerce_batch_subrequest(req).model_dump(
                        by_alias=True,
                        exclude_none=True,
                    )
                    for req in requests
                ],
                "haltOnError": halt_on_error,
            }
        )
        resp = await self._client.post(
            f"{base_path}/composite/batch",
            content=_render_payload(self._renderer, payload),
        )
        return CompositeBatchResponse.model_validate_json(resp.content)

    async def tree(
        self,
        object_name: str,
        records: list[dict[str, Any]],
        *,
        all_or_none: bool = False,
    ) -> CompositeTreeResponse:
        """Execute a hierarchical tree create request."""
        base_path = await self._base_path()
        payload = CompositeTreeRequest.model_validate(
            {"allOrNone": all_or_none, "records": _dump_records(records)}
        )
        resp = await self._client.post(
            f"{base_path}/composite/tree/{object_name}",
            content=_render_payload(self._renderer, payload),
        )
        return CompositeTreeResponse.model_validate_json(resp.content)
