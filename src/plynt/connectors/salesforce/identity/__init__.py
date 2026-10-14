"""Salesforce identity access primitives package exports."""

from __future__ import annotations

from .service import (
    AsyncSalesforceIdentityAccessService,
    SalesforceIdentityAccessService,
)

__all__ = [
    "AsyncSalesforceIdentityAccessService",
    "SalesforceIdentityAccessService",
]
