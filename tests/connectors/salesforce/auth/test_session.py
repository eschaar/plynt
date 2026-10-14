"""Cover Salesforce session auth middleware behavior."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from plynt.base.request import Request
from plynt.base.response import Response
from plynt.connectors.salesforce.auth import (
    AsyncSalesforceSessionAuthMiddleware,
    SalesforceSessionAuthMiddleware,
)
from tests.connectors.salesforce.conftest import (
    DUMMY_ACCESS_TOKEN,
    DUMMY_INSTANCE_URL,
)


class TestSalesforceSessionAuthMiddleware:
    """Exercise direct session/token middleware variants."""

    def test_sync_session_middleware_sets_authorization_header(self) -> None:
        auth = SalesforceSessionAuthMiddleware(
            access_token=DUMMY_ACCESS_TOKEN,
            instance_url=DUMMY_INSTANCE_URL,
        )
        request = Request(method="GET", url="https://example.com", headers={})

        def _next(req: Request) -> Response:
            return Response(status_code=200, headers=req.headers)

        response = auth.handle(request, _next)
        assert response.headers["Authorization"] == f"Bearer {DUMMY_ACCESS_TOKEN}"
        assert auth.instance_url == DUMMY_INSTANCE_URL

    async def test_async_session_middleware_exposes_instance_url(self) -> None:
        auth = AsyncSalesforceSessionAuthMiddleware(
            access_token=DUMMY_ACCESS_TOKEN,
            instance_url=DUMMY_INSTANCE_URL,
        )
        assert await auth.get_instance_url() == DUMMY_INSTANCE_URL
