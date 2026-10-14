"""Salesforce Metadata REST deploy services.

Provides sync and async services for the Metadata REST deploy pipeline under
``/metadata/deployRequest``.

Supported REST deploy operations:
- start deploy from ZIP package bytes
- poll deploy status (optionally with details)
- quick deploy from a validated deployment id
- cancel an in-progress deploy
- wait helpers for terminal completion
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from plynt.connectors.salesforce.constants import (
    resolve_async_api_version,
    resolve_sync_api_version,
)
from plynt.connectors.salesforce.errors import (
    MetadataDeployTimeoutError,
    SalesforceMetadataDeployError,
)
from plynt.connectors.salesforce.renderer import SalesforceRenderer
from plynt.http.client import APIClient, AsyncAPIClient
from plynt.http.renderer import Renderer
from plynt.http.service import APIService, AsyncAPIService

__all__ = [
    "AsyncSalesforceMetadataService",
    "SalesforceMetadataDeployResult",
    "SalesforceMetadataService",
]

_TERMINAL_DEPLOY_STATUSES: frozenset[str] = frozenset(
    {"Succeeded", "SucceededPartial", "Failed", "Canceled"}
)
_FAILED_DEPLOY_STATUSES: frozenset[str] = frozenset({"Failed", "Canceled"})


class SalesforceMetadataDeployResult(BaseModel):
    """Typed deploy result model for Metadata REST deploy operations."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    status: str | None = None
    done: bool | None = None
    success: bool | None = None
    error_message: str | None = Field(None, alias="errorMessage")


def _build_deploy_multipart_body(
    zip_bytes: bytes,
    options: dict[str, Any] | None,
) -> tuple[bytes, str]:
    """Build multipart/form-data body for deploy request POST."""
    boundary = f"----plynt-{uuid4().hex}"
    options_payload = json.dumps(options or {}, separators=(",", ":")).encode("utf-8")

    preamble = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="entity_content"\r\n'
        "Content-Type: application/json\r\n\r\n"
    ).encode()

    file_header = (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="package.zip"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode()

    closing = f"\r\n--{boundary}--\r\n".encode()
    body = preamble + options_payload + file_header + zip_bytes + closing
    return body, boundary


def _is_terminal(result: SalesforceMetadataDeployResult) -> bool:
    """Return whether deploy status is terminal."""
    if result.done is not None:
        return result.done
    return result.status in _TERMINAL_DEPLOY_STATUSES


def _raise_if_failed(result: SalesforceMetadataDeployResult) -> None:
    """Raise a typed error when deploy completed in a failed terminal state."""
    failed_by_status = result.status in _FAILED_DEPLOY_STATUSES
    failed_by_flag = result.success is False
    if failed_by_status or failed_by_flag:
        status = result.status or "unknown"
        detail = result.error_message or "metadata deploy failed"
        raise SalesforceMetadataDeployError(
            deploy_id=result.id,
            status=status,
            message=detail,
        )


class SalesforceMetadataService(APIService):
    """Sync service for Metadata REST deploy operations."""

    def __init__(
        self,
        client: APIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize SalesforceMetadataService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = resolve_sync_api_version(client, api_version)

    def _deploy_path(self, deploy_id: str | None = None) -> str:
        """Return metadata deploy request endpoint path."""
        base = f"/services/data/v{self._api_version}/metadata/deployRequest"
        return f"{base}/{deploy_id}" if deploy_id else base

    def start_deploy(
        self,
        zip_bytes: bytes,
        *,
        options: dict[str, Any] | None = None,
    ) -> SalesforceMetadataDeployResult:
        """Start a metadata deploy from ZIP package bytes."""
        if not zip_bytes:
            raise ValueError("zip_bytes must not be empty")

        body, boundary = _build_deploy_multipart_body(zip_bytes, options)
        resp = self._client.post(
            self._deploy_path(),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/json",
            },
            content=body,
        )
        return SalesforceMetadataDeployResult.model_validate_json(resp.content)

    def get_deploy(
        self,
        deploy_id: str,
        *,
        include_details: bool = False,
    ) -> SalesforceMetadataDeployResult:
        """Get metadata deploy status for a deployment id."""
        params = {"includeDetails": "true"} if include_details else None
        resp = self._client.get(self._deploy_path(deploy_id), params=params)
        return SalesforceMetadataDeployResult.model_validate_json(resp.content)

    def quick_deploy(self, validated_deploy_id: str) -> SalesforceMetadataDeployResult:
        """Trigger quick deploy from a validated deployment id."""
        resp = self._client.post(self._deploy_path(validated_deploy_id))
        return SalesforceMetadataDeployResult.model_validate_json(resp.content)

    def cancel_deploy(self, deploy_id: str) -> SalesforceMetadataDeployResult:
        """Cancel an in-progress metadata deployment."""
        resp = self._client.patch(
            self._deploy_path(deploy_id),
            content=json.dumps({"status": "Canceling"}).encode("utf-8"),
        )
        return SalesforceMetadataDeployResult.model_validate_json(resp.content)

    def wait_for_deploy(
        self,
        deploy_id: str,
        *,
        include_details: bool = True,
        max_wait: float = 300.0,
        poll_interval: float = 2.0,
    ) -> SalesforceMetadataDeployResult:
        """Poll metadata deploy status until terminal completion."""
        deadline = time.monotonic() + max_wait
        while True:
            result = self.get_deploy(deploy_id, include_details=include_details)
            if _is_terminal(result):
                _raise_if_failed(result)
                return result
            if time.monotonic() >= deadline:
                raise MetadataDeployTimeoutError(deploy_id=deploy_id, max_wait=max_wait)
            time.sleep(poll_interval)

    def deploy_and_wait(
        self,
        zip_bytes: bytes,
        *,
        options: dict[str, Any] | None = None,
        include_details: bool = True,
        max_wait: float = 300.0,
        poll_interval: float = 2.0,
    ) -> SalesforceMetadataDeployResult:
        """Start a deploy and wait for terminal completion."""
        started = self.start_deploy(zip_bytes, options=options)
        return self.wait_for_deploy(
            started.id,
            include_details=include_details,
            max_wait=max_wait,
            poll_interval=poll_interval,
        )


class AsyncSalesforceMetadataService(AsyncAPIService):
    """Async service for Metadata REST deploy operations."""

    def __init__(
        self,
        client: AsyncAPIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncSalesforceMetadataService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = api_version

    async def _deploy_path(self, deploy_id: str | None = None) -> str:
        """Return metadata deploy request endpoint path."""
        if self._api_version is None:
            self._api_version = await resolve_async_api_version(
                self._client,
                self._api_version,
            )
        base = f"/services/data/v{self._api_version}/metadata/deployRequest"
        return f"{base}/{deploy_id}" if deploy_id else base

    async def start_deploy(
        self,
        zip_bytes: bytes,
        *,
        options: dict[str, Any] | None = None,
    ) -> SalesforceMetadataDeployResult:
        """Start a metadata deploy from ZIP package bytes."""
        if not zip_bytes:
            raise ValueError("zip_bytes must not be empty")

        body, boundary = _build_deploy_multipart_body(zip_bytes, options)
        resp = await self._client.post(
            await self._deploy_path(),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/json",
            },
            content=body,
        )
        return SalesforceMetadataDeployResult.model_validate_json(resp.content)

    async def get_deploy(
        self,
        deploy_id: str,
        *,
        include_details: bool = False,
    ) -> SalesforceMetadataDeployResult:
        """Get metadata deploy status for a deployment id."""
        params = {"includeDetails": "true"} if include_details else None
        resp = await self._client.get(
            await self._deploy_path(deploy_id),
            params=params,
        )
        return SalesforceMetadataDeployResult.model_validate_json(resp.content)

    async def quick_deploy(
        self,
        validated_deploy_id: str,
    ) -> SalesforceMetadataDeployResult:
        """Trigger quick deploy from a validated deployment id."""
        resp = await self._client.post(await self._deploy_path(validated_deploy_id))
        return SalesforceMetadataDeployResult.model_validate_json(resp.content)

    async def cancel_deploy(self, deploy_id: str) -> SalesforceMetadataDeployResult:
        """Cancel an in-progress metadata deployment."""
        resp = await self._client.patch(
            await self._deploy_path(deploy_id),
            content=json.dumps({"status": "Canceling"}).encode("utf-8"),
        )
        return SalesforceMetadataDeployResult.model_validate_json(resp.content)

    async def wait_for_deploy(
        self,
        deploy_id: str,
        *,
        include_details: bool = True,
        max_wait: float = 300.0,
        poll_interval: float = 2.0,
    ) -> SalesforceMetadataDeployResult:
        """Poll metadata deploy status until terminal completion."""
        deadline = time.monotonic() + max_wait
        while True:
            result = await self.get_deploy(deploy_id, include_details=include_details)
            if _is_terminal(result):
                _raise_if_failed(result)
                return result
            if time.monotonic() >= deadline:
                raise MetadataDeployTimeoutError(deploy_id=deploy_id, max_wait=max_wait)
            await asyncio.sleep(poll_interval)

    async def deploy_and_wait(
        self,
        zip_bytes: bytes,
        *,
        options: dict[str, Any] | None = None,
        include_details: bool = True,
        max_wait: float = 300.0,
        poll_interval: float = 2.0,
    ) -> SalesforceMetadataDeployResult:
        """Start a deploy and wait for terminal completion."""
        started = await self.start_deploy(zip_bytes, options=options)
        return await self.wait_for_deploy(
            started.id,
            include_details=include_details,
            max_wait=max_wait,
            poll_interval=poll_interval,
        )
