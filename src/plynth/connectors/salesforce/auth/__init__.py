"""Salesforce auth middleware package exports."""

from __future__ import annotations

from .bearer import (
    AsyncSalesforceJWTBearerAuthMiddleware,
    SalesforceJWTBearerAuthMiddleware,
)
from .credentials import (
    AsyncSalesforceClientCredentialsAuthMiddleware,
    SalesforceClientCredentialsAuthMiddleware,
)
from .password import (
    AsyncSalesforcePasswordAuthMiddleware,
    SalesforcePasswordAuthMiddleware,
)
from .session import (
    AsyncSalesforceSessionAuthMiddleware,
    SalesforceSessionAuthMiddleware,
)

SalesforceOAuth2AuthMiddleware = SalesforceClientCredentialsAuthMiddleware
AsyncSalesforceOAuth2AuthMiddleware = AsyncSalesforceClientCredentialsAuthMiddleware

SalesforceOAuth2ClientCredentialsAuthMiddleware = (
    SalesforceClientCredentialsAuthMiddleware
)
SalesforceOAuth2PasswordAuthMiddleware = SalesforcePasswordAuthMiddleware
AsyncSalesforceOAuth2ClientCredentialsAuthMiddleware = (
    AsyncSalesforceClientCredentialsAuthMiddleware
)
AsyncSalesforceOAuth2PasswordAuthMiddleware = AsyncSalesforcePasswordAuthMiddleware

__all__ = [
    "AsyncSalesforceClientCredentialsAuthMiddleware",
    "AsyncSalesforceJWTBearerAuthMiddleware",
    "AsyncSalesforceOAuth2AuthMiddleware",
    "AsyncSalesforceOAuth2ClientCredentialsAuthMiddleware",
    "AsyncSalesforceOAuth2PasswordAuthMiddleware",
    "AsyncSalesforcePasswordAuthMiddleware",
    "AsyncSalesforceSessionAuthMiddleware",
    "SalesforceClientCredentialsAuthMiddleware",
    "SalesforceJWTBearerAuthMiddleware",
    "SalesforceOAuth2AuthMiddleware",
    "SalesforceOAuth2ClientCredentialsAuthMiddleware",
    "SalesforceOAuth2PasswordAuthMiddleware",
    "SalesforcePasswordAuthMiddleware",
    "SalesforceSessionAuthMiddleware",
]
