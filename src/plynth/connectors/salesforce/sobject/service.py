"""Salesforce SObject REST API service.

Provides a generic, framework-agnostic service for CRUD operations on any
Salesforce SObject via the Salesforce Platform REST API.

The service targets the SObject REST API under:

    /services/data/v{version}/sobjects/{Object}/
    /services/data/v{version}/sobjects/{Object}/{id}
    /services/data/v{version}/sobjects/{Object}/{field}/{value}
    /services/data/v{version}/sobjects/{Object}/describe

Authentication (OAuth2 Client Credentials, bearer token, etc.) and retry
are handled by the transport layer. The service delegates all HTTP calls
to the injected ``APIClient`` / ``AsyncAPIClient``, which adds JSON headers
and raises typed errors for 4xx/5xx responses.

Reference:
    Salesforce Platform REST API Developer Guide
    — Working with sObjects
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, cast
from urllib.parse import quote

from plynth.connectors.salesforce.constants import (
    DEFAULT_API_VERSION,
    SALESFORCE_ID_RE,
    resolve_async_api_version,
    resolve_sync_api_version,
)
from plynth.connectors.salesforce.models import (
    SObjectCreateResult,
    SObjectPayload,
)
from plynth.connectors.salesforce.renderer import SalesforceRenderer
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import Renderer
from plynth.http.service import APIService, AsyncAPIService

__all__ = [
    "DEFAULT_API_VERSION",
    "AsyncSalesforceObjectService",
    "SalesforceObjectService",
]


# ---------------------------------------------------------------------------
# Shared mixin — pure helpers, no I/O
# ---------------------------------------------------------------------------


class _SalesforceObjectServiceMixin:
    """URL-building helpers shared by sync and async object service classes."""

    _object_name: str
    _api_version: str | None

    @staticmethod
    def _is_salesforce_id(value: str) -> bool:
        """Return ``True`` when *value* matches the Salesforce record ID format."""
        return bool(SALESFORCE_ID_RE.fullmatch(value))

    def _sobject_path(self, *parts: str) -> str:
        """Build a URL path under the SObject resource root."""
        if self._api_version is None:  # pragma: no cover
            raise RuntimeError("SObject path requested before API version resolution")
        base = f"/services/data/v{self._api_version}/sobjects/{self._object_name}"
        if parts:
            encoded = "/".join(quote(str(p), safe="") for p in parts)
            return f"{base}/{encoded}"
        return base


# ---------------------------------------------------------------------------
# Sync service
# ---------------------------------------------------------------------------


class SalesforceObjectService(_SalesforceObjectServiceMixin, APIService):
    """Generic service for Salesforce SObject CRUD via the REST API.

    Targets the Salesforce Platform REST API SObject resource. All I/O is
    delegated to the injected ``APIClient``, which handles JSON headers,
    typed HTTP error raising, and transport-level concerns (auth, retry).

    The service is intentionally generic — it carries no domain knowledge
    about specific SObject types. Concrete services for ``Account``,
    ``Contact``, etc. inject the appropriate ``object_name`` at construction
    time or subclass this service and set ``object_name`` themselves.

    HTTP behaviour per operation:

    +---------+--------------------------------------------------------------+
    | Method  | Salesforce response                                          |
    +=========+==============================================================+
    | get     | 200 OK — SObject field values as JSON                        |
    +---------+--------------------------------------------------------------+
    | create  | 201 Created — ``{"id": "...", "success": true, "errors": []}``|
    +---------+--------------------------------------------------------------+
    | update  | 204 No Content — no body returned                            |
    +---------+--------------------------------------------------------------+
    | upsert  | 201 Created (new) or 204 No Content (updated)                |
    +---------+--------------------------------------------------------------+
    | delete  | 204 No Content — no body returned                            |
    +---------+--------------------------------------------------------------+
    | describe| 200 OK — SObject metadata as JSON                            |
    +---------+--------------------------------------------------------------+

    Args:
        client: Configured ``APIClient`` pointing at the Salesforce instance
            base URL (e.g. ``"https://myorg.my.salesforce.com"``).
        object_name: Salesforce API name of the SObject (e.g. ``"Account"``,
            ``"Contact"``, ``"My_Object__c"``). Case-sensitive.
        api_version: Salesforce REST API version to target (default
            ``"59.0"``). Must match a version enabled on the connected app.
        renderer: Body serialiser used for write operations. Defaults to
            ``SalesforceRenderer``, which handles datetime, Decimal, and UUID
            values and applies ``SObjectPayload`` field-name mapping. Inject a
            custom renderer to override serialisation behaviour.

    Example::

        from plynth.http.client import APIClient
        from plynth.http.transport import HttpxSyncTransport
        from plynth.connectors.salesforce.sobject import SalesforceObjectService

        transport = HttpxSyncTransport.from_settings(settings)
        client = APIClient(
            base_url="https://myorg.my.salesforce.com",
            transport=transport,
        )
        svc = SalesforceObjectService(client, "Account")

        account = svc.get("001xx000003GYWJAA4")
        new_id = svc.create({"Name": "ACME Corp"})["id"]
        svc.update("001xx000003GYWJAA4", {"Phone": "+31201234567"})
        svc.delete("001xx000003GYWJAA4")

    """

    def __init__(
        self,
        client: APIClient,
        object_name: str,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialise the service with a client, SObject name, and API version."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._object_name = object_name
        self._api_version = resolve_sync_api_version(client, api_version)

    # ------------------------------------------------------------------
    # SObject REST API operations — private implementation
    # ------------------------------------------------------------------
    # Each public method below has a matching private ``_<method>`` that
    # performs the actual HTTP call.  Subclasses can override the private
    # methods to customise behaviour (pre/post processing, custom fields,
    # different URL conventions, etc.) while the public methods — and any
    # decorators applied to them — remain unchanged.
    # ------------------------------------------------------------------

    def _get(
        self,
        record_id: str,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}/{id}"""
        if not self._is_salesforce_id(record_id):
            raise ValueError(f"Invalid Salesforce record ID: {record_id!r}")
        params = {"fields": ",".join(fields)} if fields else None
        resp = self._client.get(
            self._sobject_path(record_id),
            params=params,
        )
        return cast(dict[str, Any], json.loads(resp.content))

    def _get_by_external_id(
        self,
        external_id_field: str,
        external_id_value: str,
    ) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}/{ExternalIdField}/{value}"""
        resp = self._client.get(
            self._sobject_path(external_id_field, external_id_value),
        )
        return cast(dict[str, Any], json.loads(resp.content))

    def _create(self, data: dict[str, Any] | SObjectPayload) -> SObjectCreateResult:
        """Execute POST /sobjects/{Object}/"""
        payload = self._renderer.render(data)
        resp = self._client.post(
            self._sobject_path(),
            content=payload,
        )
        return SObjectCreateResult.model_validate(json.loads(resp.content))

    def _update(self, record_id: str, data: dict[str, Any] | SObjectPayload) -> None:
        """Execute PATCH /sobjects/{Object}/{id}"""
        if not self._is_salesforce_id(record_id):
            raise ValueError(f"Invalid Salesforce record ID: {record_id!r}")
        self._client.patch(
            self._sobject_path(record_id),
            content=self._renderer.render(data),
        )

    def _upsert(
        self,
        external_id_field: str,
        external_id_value: str,
        data: dict[str, Any] | SObjectPayload,
    ) -> SObjectCreateResult | None:
        """Execute PATCH /sobjects/{Object}/{ExternalIdField}/{value}"""
        resp = self._client.patch(
            self._sobject_path(external_id_field, external_id_value),
            content=self._renderer.render(data),
        )
        if resp.content:
            return SObjectCreateResult.model_validate(json.loads(resp.content))
        return None

    def _delete(self, record_id: str) -> None:
        """Execute DELETE /sobjects/{Object}/{id}"""
        if not self._is_salesforce_id(record_id):
            raise ValueError(f"Invalid Salesforce record ID: {record_id!r}")
        self._client.delete(self._sobject_path(record_id))

    def _describe(self) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}/describe"""
        resp = self._client.get(self._sobject_path("describe"))
        return cast(dict[str, Any], json.loads(resp.content))

    def _metadata(self) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}"""
        resp = self._client.get(self._sobject_path())
        return cast(dict[str, Any], json.loads(resp.content))

    def _describe_layout(self, record_id: str) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}/describe/layouts/{record_id}"""
        if not self._is_salesforce_id(record_id):
            raise ValueError(f"Invalid Salesforce record ID: {record_id!r}")
        resp = self._client.get(self._sobject_path("describe", "layouts", record_id))
        return cast(dict[str, Any], json.loads(resp.content))

    def _deleted(self, start: datetime, end: datetime) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}/deleted with start/end window"""
        resp = self._client.get(
            self._sobject_path("deleted"),
            params={"start": start.isoformat(), "end": end.isoformat()},
        )
        return cast(dict[str, Any], json.loads(resp.content))

    def _updated(self, start: datetime, end: datetime) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}/updated with start/end window"""
        resp = self._client.get(
            self._sobject_path("updated"),
            params={"start": start.isoformat(), "end": end.isoformat()},
        )
        return cast(dict[str, Any], json.loads(resp.content))

    # ------------------------------------------------------------------
    # SObject REST API operations — public interface
    # ------------------------------------------------------------------

    def get(
        self,
        record_id: str,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Retrieve a single SObject record by its Salesforce record ID.

        Calls ``GET /services/data/v{version}/sobjects/{Object}/{id}``.

        To look up a record by an external ID field, use
        ``get_by_external_id()`` instead.

        Args:
            record_id: 18-character (or 15-character) Salesforce record ID.
            fields: Optional list of field API names to include in the
                response. When omitted, Salesforce returns all fields
                accessible to the running user.

        Returns:
            A dict containing the SObject field values as returned by
            Salesforce (keys are field API names).

        Raises:
            NotFoundError: No record with *record_id* exists (HTTP 404).
            ForbiddenError: Insufficient field-level security (HTTP 403).

        """
        return self._get(record_id, fields)

    def get_by_external_id(
        self,
        external_id_field: str,
        external_id_value: str,
    ) -> dict[str, Any]:
        """Retrieve an SObject record by an external ID field value.

        Calls ``GET /sobjects/{Object}/{ExternalIdField}/{value}``.

        Args:
            external_id_field: API name of the external ID field defined in
                Salesforce (e.g. ``"My_External_Id__c"``).

        Raises:
            NotFoundError: No record matches the given external ID (HTTP 404).

        """
        return self._get_by_external_id(external_id_field, external_id_value)

    def create(self, data: dict[str, Any] | SObjectPayload) -> SObjectCreateResult:
        """Create a new SObject record.

        Calls ``POST /sobjects/{Object}/``. Returns the Salesforce-assigned
        record ID and success status on HTTP 201.

        Args:
            data: Field values for the new record. Either a plain dict with
                Salesforce field API names as keys, or an ``SObjectPayload``
                instance whose ``to_payload()`` method handles the mapping.

        Returns:
            An ``SObjectCreateResult`` with ``id``, ``success``, and
            ``errors``.

        Raises:
            BadRequestError: Required fields are missing (HTTP 400).
            UnprocessableEntityError: Field values are invalid (HTTP 422).

        """
        return self._create(data)

    def update(self, record_id: str, data: dict[str, Any] | SObjectPayload) -> None:
        """Partially update an existing SObject record.

        Calls ``PATCH /sobjects/{Object}/{id}``. Only the fields supplied in
        *data* are modified; omitted fields retain their current values.
        Salesforce returns 204 No Content on success.

        Args:
            data: Fields to update. Either a plain dict with Salesforce field
                API names as keys, or an ``SObjectPayload`` instance.

        Raises:
            NotFoundError: No record with *record_id* exists (HTTP 404).
            ForbiddenError: The user lacks update permission (HTTP 403).

        """
        self._update(record_id, data)

    def upsert(
        self,
        external_id_field: str,
        external_id_value: str,
        data: dict[str, Any] | SObjectPayload,
    ) -> SObjectCreateResult | None:
        """Create or update an SObject record identified by an external ID.

        Calls ``PATCH /sobjects/{Object}/{ExternalIdField}/{value}``.
        Salesforce returns:

        - **201 Created** with an ``SObjectCreateResult`` when a new record is
          created.
        - **204 No Content** when an existing record is updated in place
          (returns ``None``).

        Args:
            external_id_field: API name of the external ID field.
            data: Field values to set on the record. Either a plain dict or
                an ``SObjectPayload`` instance.

        Returns:
            An ``SObjectCreateResult`` if a new record was created;
            ``None`` if an existing record was updated.

        """
        return self._upsert(external_id_field, external_id_value, data)

    def delete(self, record_id: str) -> None:
        """Delete an SObject record by its Salesforce record ID.

        Calls ``DELETE /sobjects/{Object}/{id}``. Salesforce returns 204 No
        Content on success.

        Raises:
            NotFoundError: No record with *record_id* exists (HTTP 404).
            ForbiddenError: The user lacks delete permission (HTTP 403).

        """
        self._delete(record_id)

    def describe(self) -> dict[str, Any]:
        """Return the metadata description for this SObject type.

        Calls ``GET /sobjects/{Object}/describe``. The response contains
        field metadata, record types, child relationships, and other
        descriptive information as returned by Salesforce.

        Returns:
            A dict with the full SObject metadata (fields, relationships,
            record types, etc.).

        """
        return self._describe()

    def metadata(self) -> dict[str, Any]:
        """Return metadata for this SObject root resource.

        Calls ``GET /sobjects/{Object}``.

        """
        return self._metadata()

    def describe_layout(self, record_id: str) -> dict[str, Any]:
        """Return the SObject layout for a record.

        Calls ``GET /sobjects/{Object}/describe/layouts/{record_id}``.

        """
        return self._describe_layout(record_id)

    def deleted(self, start: datetime, end: datetime) -> dict[str, Any]:
        """Return deleted records in a time window.

        Calls ``GET /sobjects/{Object}/deleted`` with ``start`` and ``end``
        query parameters.

        Args:
            start: Start timestamp for the query window.
            end: End timestamp for the query window.

        """
        return self._deleted(start, end)

    def updated(self, start: datetime, end: datetime) -> dict[str, Any]:
        """Return updated records in a time window.

        Calls ``GET /sobjects/{Object}/updated`` with ``start`` and ``end``
        query parameters.

        Args:
            start: Start timestamp for the query window.
            end: End timestamp for the query window.

        """
        return self._updated(start, end)


# ---------------------------------------------------------------------------
# Async service
# ---------------------------------------------------------------------------


class AsyncSalesforceObjectService(_SalesforceObjectServiceMixin, AsyncAPIService):
    """Async service for Salesforce SObject CRUD via the REST API.

    Async counterpart of ``SalesforceObjectService``. All endpoint methods
    are coroutines; inject an ``AsyncAPIClient`` (or
    ``AsyncSalesforceAPIClient``) backed by an async transport.

    Example::

        from plynth.http.transport import HttpxAsyncTransport
        from plynth.connectors.salesforce.client import AsyncSalesforceAPIClient
        from plynth.connectors.salesforce.sobject import AsyncSalesforceObjectService

        transport = HttpxAsyncTransport(middlewares=[auth])
        client = AsyncSalesforceAPIClient(auth=auth, transport=transport)
        svc = AsyncSalesforceObjectService(client, "Account")

        account = await svc.get("001xx000003GYWJAA4")
        result = await svc.create({"Name": "ACME Corp"})

    """

    def __init__(
        self,
        client: AsyncAPIClient,
        object_name: str,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialise the async service with a client, SObject name, and version."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._object_name = object_name
        self._api_version = api_version

    async def _sobject_path_async(self, *parts: str) -> str:
        """Build a URL path under the SObject root with lazy version discovery."""
        if self._api_version is None:
            self._api_version = await resolve_async_api_version(
                self._client,
                self._api_version,
            )
        return self._sobject_path(*parts)

    # ------------------------------------------------------------------
    # SObject REST API operations — private async implementation
    # ------------------------------------------------------------------

    async def _get(
        self,
        record_id: str,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}/{id}"""
        if not self._is_salesforce_id(record_id):
            raise ValueError(f"Invalid Salesforce record ID: {record_id!r}")
        params = {"fields": ",".join(fields)} if fields else None
        resp = await self._client.get(
            await self._sobject_path_async(record_id),
            params=params,
        )
        return cast(dict[str, Any], json.loads(resp.content))

    async def _get_by_external_id(
        self,
        external_id_field: str,
        external_id_value: str,
    ) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}/{ExternalIdField}/{value}"""
        resp = await self._client.get(
            await self._sobject_path_async(external_id_field, external_id_value),
        )
        return cast(dict[str, Any], json.loads(resp.content))

    async def _create(
        self, data: dict[str, Any] | SObjectPayload
    ) -> SObjectCreateResult:
        """Execute POST /sobjects/{Object}/"""
        payload = self._renderer.render(data)
        resp = await self._client.post(
            await self._sobject_path_async(),
            content=payload,
        )
        return SObjectCreateResult.model_validate(json.loads(resp.content))

    async def _update(
        self, record_id: str, data: dict[str, Any] | SObjectPayload
    ) -> None:
        """Execute PATCH /sobjects/{Object}/{id}"""
        if not self._is_salesforce_id(record_id):
            raise ValueError(f"Invalid Salesforce record ID: {record_id!r}")
        await self._client.patch(
            await self._sobject_path_async(record_id),
            content=self._renderer.render(data),
        )

    async def _upsert(
        self,
        external_id_field: str,
        external_id_value: str,
        data: dict[str, Any] | SObjectPayload,
    ) -> SObjectCreateResult | None:
        """Execute PATCH /sobjects/{Object}/{ExternalIdField}/{value}"""
        resp = await self._client.patch(
            await self._sobject_path_async(external_id_field, external_id_value),
            content=self._renderer.render(data),
        )
        if resp.content:
            return SObjectCreateResult.model_validate(json.loads(resp.content))
        return None

    async def _delete(self, record_id: str) -> None:
        """Execute DELETE /sobjects/{Object}/{id}"""
        if not self._is_salesforce_id(record_id):
            raise ValueError(f"Invalid Salesforce record ID: {record_id!r}")
        await self._client.delete(await self._sobject_path_async(record_id))

    async def _describe(self) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}/describe"""
        resp = await self._client.get(await self._sobject_path_async("describe"))
        return cast(dict[str, Any], json.loads(resp.content))

    async def _metadata(self) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}"""
        resp = await self._client.get(await self._sobject_path_async())
        return cast(dict[str, Any], json.loads(resp.content))

    async def _describe_layout(self, record_id: str) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}/describe/layouts/{record_id}"""
        if not self._is_salesforce_id(record_id):
            raise ValueError(f"Invalid Salesforce record ID: {record_id!r}")
        resp = await self._client.get(
            await self._sobject_path_async("describe", "layouts", record_id),
        )
        return cast(dict[str, Any], json.loads(resp.content))

    async def _deleted(self, start: datetime, end: datetime) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}/deleted with start/end window"""
        resp = await self._client.get(
            await self._sobject_path_async("deleted"),
            params={"start": start.isoformat(), "end": end.isoformat()},
        )
        return cast(dict[str, Any], json.loads(resp.content))

    async def _updated(self, start: datetime, end: datetime) -> dict[str, Any]:
        """Execute GET /sobjects/{Object}/updated with start/end window"""
        resp = await self._client.get(
            await self._sobject_path_async("updated"),
            params={"start": start.isoformat(), "end": end.isoformat()},
        )
        return cast(dict[str, Any], json.loads(resp.content))

    # ------------------------------------------------------------------
    # SObject REST API operations — public async interface
    # ------------------------------------------------------------------

    async def get(
        self,
        record_id: str,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Retrieve a single SObject record by its Salesforce record ID.

        Args:
            record_id: 18-character (or 15-character) Salesforce record ID.
            fields: Optional list of field API names to include in the
                response.

        Returns:
            A dict containing the SObject field values.

        Raises:
            NotFoundError: No record with *record_id* exists (HTTP 404).
            UnauthorizedError: The access token has expired (HTTP 401).

        """
        return await self._get(record_id, fields)

    async def get_by_external_id(
        self,
        external_id_field: str,
        external_id_value: str,
    ) -> dict[str, Any]:
        """Retrieve an SObject record by an external ID field value.

        Args:
            external_id_field: API name of the external ID field.

        Raises:
            NotFoundError: No record matches the given external ID (HTTP 404).

        """
        return await self._get_by_external_id(external_id_field, external_id_value)

    async def create(
        self, data: dict[str, Any] | SObjectPayload
    ) -> SObjectCreateResult:
        """Create a new SObject record.

        Args:
            data: Field values for the new record.

        Returns:
            An ``SObjectCreateResult`` with ``id``, ``success``, and
            ``errors``.

        """
        return await self._create(data)

    async def update(
        self, record_id: str, data: dict[str, Any] | SObjectPayload
    ) -> None:
        """Partially update an existing SObject record.

        Args:
            data: Fields to update.

        Raises:
            NotFoundError: No record with *record_id* exists (HTTP 404).

        """
        await self._update(record_id, data)

    async def upsert(
        self,
        external_id_field: str,
        external_id_value: str,
        data: dict[str, Any] | SObjectPayload,
    ) -> SObjectCreateResult | None:
        """Create or update an SObject record identified by an external ID.

        Returns:
            An ``SObjectCreateResult`` if a new record was created;
            ``None`` if an existing record was updated.

        """
        return await self._upsert(external_id_field, external_id_value, data)

    async def delete(self, record_id: str) -> None:
        """Delete an SObject record by its Salesforce record ID.

        Raises:
            NotFoundError: No record with *record_id* exists (HTTP 404).

        """
        await self._delete(record_id)

    async def describe(self) -> dict[str, Any]:
        """Return the metadata description for this SObject type.

        Returns:
            A dict with the full SObject metadata.

        """
        return await self._describe()

    async def metadata(self) -> dict[str, Any]:
        """Return metadata for this SObject root resource."""
        return await self._metadata()

    async def describe_layout(self, record_id: str) -> dict[str, Any]:
        """Return the SObject layout for a record."""
        return await self._describe_layout(record_id)

    async def deleted(self, start: datetime, end: datetime) -> dict[str, Any]:
        """Return deleted records in a time window."""
        return await self._deleted(start, end)

    async def updated(self, start: datetime, end: datetime) -> dict[str, Any]:
        """Return updated records in a time window."""
        return await self._updated(start, end)
