"""Salesforce typed data models."""

from __future__ import annotations

from .schemas import (
    SalesforceApiUsage,
    SalesforceApiVersion,
    SalesforceGlobalDescribeResponse,
    SalesforceLimit,
    SalesforceLimitsResponse,
    SalesforceQueryResponse,
    SalesforceSearchRecord,
    SalesforceSearchResponse,
    SalesforceSObjectSummary,
    SObjectCreateResult,
    SObjectError,
    SObjectPayload,
)

__all__ = [
    "SObjectCreateResult",
    "SObjectError",
    "SObjectPayload",
    "SalesforceApiUsage",
    "SalesforceApiVersion",
    "SalesforceGlobalDescribeResponse",
    "SalesforceLimit",
    "SalesforceLimitsResponse",
    "SalesforceQueryResponse",
    "SalesforceSObjectSummary",
    "SalesforceSearchRecord",
    "SalesforceSearchResponse",
]
