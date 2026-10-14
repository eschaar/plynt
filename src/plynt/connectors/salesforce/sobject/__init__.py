"""Salesforce SObject service package exports."""

from __future__ import annotations

from .service import (
    DEFAULT_API_VERSION,
    AsyncSalesforceObjectService,
    SalesforceObjectService,
)

__all__ = [
    "DEFAULT_API_VERSION",
    "AsyncSalesforceObjectService",
    "SalesforceObjectService",
]
