# Share Salesforce auth in a FastAPI lifespan

Install `plynt[fastapi,salesforce]`. Use one Salesforce auth middleware instance
for both the outbound transport and `AsyncSalesforceAPIClient`: the client uses
its cached `instance_url`, while the transport uses its cached token.

The generic `PlyntLifespan` manages named transports, not connector-owned auth
and client relationships. Use an application lifespan for this composition;
no Salesforce dependency or helper belongs in the framework-agnostic core.

## Create resources at startup

Set `SF_CLIENT_ID`, `SF_CLIENT_SECRET`, and `SF_TOKEN_URL` through your runtime
secret/configuration provider. Missing values fail startup rather than silently
disabling authentication. Choose a token endpoint trusted by your application.

```python
import os
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, Request

from plynt.connectors.salesforce.auth import (
    AsyncSalesforceClientCredentialsAuthMiddleware,
)
from plynt.connectors.salesforce.client import AsyncSalesforceAPIClient
from plynt.http.transport import HttpxAsyncTransport


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    client_id = os.environ["SF_CLIENT_ID"]
    client_secret = os.environ["SF_CLIENT_SECRET"]
    token_url = os.environ["SF_TOKEN_URL"]
    async with AsyncExitStack() as resources:
        auth = AsyncSalesforceClientCredentialsAuthMiddleware(
            client_id=client_id,
            client_secret=client_secret,
            token_url=token_url,
        )
        resources.push_async_callback(auth.aclose)
        transport = HttpxAsyncTransport(middlewares=[auth])
        resources.push_async_callback(transport.aclose)
        client = AsyncSalesforceAPIClient(auth=auth, transport=transport)
        app.state.salesforce = client
        try:
            yield
        finally:
            del app.state.salesforce


def get_salesforce_client(request: Request) -> AsyncSalesforceAPIClient:
    client = getattr(request.app.state, "salesforce", None)
    if not isinstance(client, AsyncSalesforceAPIClient):
        raise RuntimeError("Salesforce client is unavailable outside app lifespan")
    return client


app = FastAPI(lifespan=lifespan)
```

Use `Depends(get_salesforce_client)` on async endpoints, then construct services
from the resolved client. The dependency returns the same app-scoped client
without creating another auth middleware or HTTP connection pool.

`AsyncExitStack` registers cleanup immediately after construction. Shutdown,
exceptions during startup, and errors leaving the lifespan close the API
transport first, then the token transport owned by auth. No explicit client
close is needed: this composition owns its transport directly.

## Lifetime and concurrency

Create these objects inside startup, not as module globals or per request.
Each process and app lifespan gets its own auth cache, lock, and transports.
Share them only within that event loop; do not share an async auth object across
worker processes, independent event loops, or threads.

Token fetching remains lazy. The first request resolves the Salesforce
`instance_url`; concurrent requests share the auth lock and cached token.
There is no startup network call in this example. If your application requires
an early credential check, explicitly await `auth.get_instance_url()` before
publishing the client; failed startup still runs registered cleanup.

Drain in-flight calls before leaving the lifespan. Do not use the saved client
after shutdown. Use a separate resource bundle per org or credential set.

JWT Bearer uses the same ownership pattern with
`AsyncSalesforceJWTBearerAuthMiddleware`; configure it according to the
[authentication guide](authenticate.md#jwt-bearer-flow-recommended).

## Errors and verification

Token failures use `AuthenticationError`; network failures use typed transport
errors. Install [FastAPI error handlers](../../../../adapters/fastapi/configure-error-envelopes.md)
when your application wants plynt's external error mapping.

The repository tests execute this exact example with HTTP-level mocks. They
verify concurrent token reuse, shared instance URL and authorization, repeated
lifespans, and cleanup after startup or handler failures without Salesforce
network calls.
