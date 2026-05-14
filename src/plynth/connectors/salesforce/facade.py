"""Ergonomic Salesforce SObject API facade.

This module provides thin facade classes that offer concise SObject ergonomics
while delegating all I/O and error handling to the existing client and
service layers.
"""

from __future__ import annotations

from plynth.connectors.salesforce.agent import (
    AsyncSalesforceAgentService,
    SalesforceAgentService,
)
from plynth.connectors.salesforce.ai import (
    AsyncSalesforceModelsService,
    SalesforceModelsService,
)
from plynth.connectors.salesforce.apex import (
    AsyncSalesforceApexRestService,
    SalesforceApexRestService,
)
from plynth.connectors.salesforce.bulk import (
    AsyncSalesforceBulkService,
    SalesforceBulkService,
)
from plynth.connectors.salesforce.composite import (
    AsyncSalesforceCompositeService,
    SalesforceCompositeService,
)
from plynth.connectors.salesforce.identity import (
    AsyncSalesforceIdentityAccessService,
    SalesforceIdentityAccessService,
)
from plynth.connectors.salesforce.lookup import (
    AsyncLookupService,
    LookupType,
    SyncLookupService,
    create_async_lookup_service,
    create_sync_lookup_service,
)
from plynth.connectors.salesforce.metadata import (
    AsyncSalesforceMetadataService,
    SalesforceMetadataService,
)
from plynth.connectors.salesforce.query import (
    AsyncSalesforceObjectQueryService,
    AsyncSalesforceQueryService,
    SalesforceObjectQueryService,
    SalesforceQueryService,
)
from plynth.connectors.salesforce.search import (
    AsyncSalesforceSearchService,
    SalesforceSearchService,
)
from plynth.connectors.salesforce.sobject import (
    AsyncSalesforceObjectService,
    SalesforceObjectService,
)
from plynth.connectors.salesforce.utility import (
    AsyncSalesforceUtilityService,
    SalesforceUtilityService,
)
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import Renderer

__all__ = [
    "AsyncSalesforceAPIFacade",
    "LookupType",
    "SalesforceAPIFacade",
]


class SalesforceAPIFacade:
    """Facade for constructing sync Salesforce services with concise syntax.

    The facade keeps concise ergonomics while preserving Plynth's architecture
    by delegating to the underlying service layers.
    """

    def __init__(self, client: APIClient) -> None:
        """Initialize SalesforceAPIFacade."""
        self._client = client

    def sobject(
        self,
        object_name: str,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> SalesforceObjectService:
        """Return a typed service bound to a specific Salesforce object."""
        return SalesforceObjectService(
            self._client,
            object_name,
            api_version=api_version,
            renderer=renderer,
        )

    def utility(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> SalesforceUtilityService:
        """Return a sync service for Salesforce utility REST endpoints."""
        return SalesforceUtilityService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def query(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> SalesforceQueryService:
        """Return a sync service for Salesforce SOQL query endpoints."""
        return SalesforceQueryService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def object_query(
        self,
        object_name: str,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> SalesforceObjectQueryService:
        """Return a sync object-scoped SOQL query service."""
        return SalesforceObjectQueryService(
            self._client,
            object_name,
            api_version=api_version,
            renderer=renderer,
        )

    def search(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> SalesforceSearchService:
        """Return a sync service for Salesforce SOSL search endpoints."""
        return SalesforceSearchService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def models(
        self,
        *,
        renderer: Renderer | None = None,
    ) -> SalesforceModelsService:
        """Return a sync service for Salesforce Models API endpoints."""
        return SalesforceModelsService(
            self._client,
            renderer=renderer,
        )

    def agent(
        self,
        *,
        renderer: Renderer | None = None,
    ) -> SalesforceAgentService:
        """Return a sync service for Salesforce Agent API endpoints."""
        return SalesforceAgentService(
            self._client,
            renderer=renderer,
        )

    def bulk(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> SalesforceBulkService:
        """Return a sync service for Salesforce Bulk API 2.0 jobs."""
        return SalesforceBulkService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def composite(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> SalesforceCompositeService:
        """Return a sync service for Salesforce composite REST endpoints."""
        return SalesforceCompositeService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def apex_rest(
        self,
        *,
        renderer: Renderer | None = None,
    ) -> SalesforceApexRestService:
        """Return a sync service for Salesforce Apex REST endpoints."""
        return SalesforceApexRestService(
            self._client,
            renderer=renderer,
        )

    def metadata(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> SalesforceMetadataService:
        """Return a sync service for Metadata REST deploy operations."""
        return SalesforceMetadataService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def identity_access(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> SalesforceIdentityAccessService:
        """Return a sync service for generic identity access primitives."""
        return SalesforceIdentityAccessService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def lookup(
        self,
        kind: LookupType,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> SyncLookupService:
        """Return a sync lookup service selected by lookup kind."""
        return create_sync_lookup_service(
            client=self._client,
            kind=kind,
            api_version=api_version,
            renderer=renderer,
        )


class AsyncSalesforceAPIFacade:
    """Async facade for constructing async Salesforce services."""

    def __init__(self, client: AsyncAPIClient) -> None:
        """Initialize AsyncSalesforceAPIFacade."""
        self._client = client

    def sobject(
        self,
        object_name: str,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> AsyncSalesforceObjectService:
        """Return an async service bound to a specific Salesforce object."""
        return AsyncSalesforceObjectService(
            self._client,
            object_name,
            api_version=api_version,
            renderer=renderer,
        )

    def utility(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> AsyncSalesforceUtilityService:
        """Return an async service for Salesforce utility REST endpoints."""
        return AsyncSalesforceUtilityService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def query(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> AsyncSalesforceQueryService:
        """Return an async service for Salesforce SOQL query endpoints."""
        return AsyncSalesforceQueryService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def object_query(
        self,
        object_name: str,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> AsyncSalesforceObjectQueryService:
        """Return an async object-scoped SOQL query service."""
        return AsyncSalesforceObjectQueryService(
            self._client,
            object_name,
            api_version=api_version,
            renderer=renderer,
        )

    def search(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> AsyncSalesforceSearchService:
        """Return an async service for Salesforce SOSL search endpoints."""
        return AsyncSalesforceSearchService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def models(
        self,
        *,
        renderer: Renderer | None = None,
    ) -> AsyncSalesforceModelsService:
        """Return an async service for Salesforce Models API endpoints."""
        return AsyncSalesforceModelsService(
            self._client,
            renderer=renderer,
        )

    def agent(
        self,
        *,
        renderer: Renderer | None = None,
    ) -> AsyncSalesforceAgentService:
        """Return an async service for Salesforce Agent API endpoints."""
        return AsyncSalesforceAgentService(
            self._client,
            renderer=renderer,
        )

    def bulk(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> AsyncSalesforceBulkService:
        """Return an async service for Salesforce Bulk API 2.0 jobs."""
        return AsyncSalesforceBulkService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def composite(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> AsyncSalesforceCompositeService:
        """Return an async service for Salesforce composite REST endpoints."""
        return AsyncSalesforceCompositeService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def apex_rest(
        self,
        *,
        renderer: Renderer | None = None,
    ) -> AsyncSalesforceApexRestService:
        """Return an async service for Salesforce Apex REST endpoints."""
        return AsyncSalesforceApexRestService(
            self._client,
            renderer=renderer,
        )

    def metadata(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> AsyncSalesforceMetadataService:
        """Return an async service for Metadata REST deploy operations."""
        return AsyncSalesforceMetadataService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def identity_access(
        self,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> AsyncSalesforceIdentityAccessService:
        """Return an async service for generic identity access primitives."""
        return AsyncSalesforceIdentityAccessService(
            self._client,
            api_version=api_version,
            renderer=renderer,
        )

    def lookup(
        self,
        kind: LookupType,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> AsyncLookupService:
        """Return an async lookup service selected by lookup kind."""
        return create_async_lookup_service(
            client=self._client,
            kind=kind,
            api_version=api_version,
            renderer=renderer,
        )
