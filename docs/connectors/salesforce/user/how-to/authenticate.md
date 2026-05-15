# How to authenticate with Salesforce

All Salesforce OAuth2 flows require a **Connected App** (or External Client
App) registered in Salesforce Setup. The app provides the `client_id`
(Consumer Key) and, depending on the flow, either a shared `client_secret`
or an uploaded certificate for JWT assertion verification.

| Flow                                               | Best for                   | Shared secret?         |
| -------------------------------------------------- | -------------------------- | ---------------------- |
| [JWT Bearer](#jwt-bearer-flow-recommended)         | Server-to-server, all orgs | No — uses RSA key pair |
| [Client Credentials](#client-credentials-flow)     | Simple machine-to-machine  | Yes                    |
| [Username/Password](#usernamepassword-flow-legacy) | Legacy orgs only           | Yes                    |
| [Session token](#session-token-edge-case)          | External token management  | N/A                    |

______________________________________________________________________

## JWT Bearer flow (recommended)

JWT Bearer is the Salesforce-recommended method for automated server-to-server
integrations. It uses an RSA key pair instead of a shared secret:

- Upload the **public certificate** to the Connected App in Salesforce Setup.
- Store the **private key** in your runtime secret store (environment variable,
  secrets manager). Never hardcode or commit it.
- Plynth signs a fresh JWT assertion on each token fetch and sends it to the
  token endpoint. Salesforce verifies the signature against the uploaded
  certificate.

This flow is mandatory for orgs created Summer '23 or later where the
Username/Password flow is blocked by default.

```python
import os

from plynth.connectors.salesforce.auth import SalesforceJWTBearerAuthMiddleware
from plynth.connectors.salesforce.client import SalesforceAPIClient
from plynth.connectors.salesforce.facade import SalesforceAPIFacade
from plynth.http.transport import HttpxSyncTransport

auth = SalesforceJWTBearerAuthMiddleware(
    client_id=os.environ["SF_CLIENT_ID"],         # Consumer Key of the Connected App
    username=os.environ["SF_USERNAME"],           # Salesforce username to run as
    private_key=os.environ["SF_PRIVATE_KEY_PEM"], # RSA private key, PEM-encoded
    token_url="https://login.salesforce.com/services/oauth2/token",
)
transport = HttpxSyncTransport(middlewares=[auth])
client = SalesforceAPIClient(auth=auth, transport=transport)
sf = SalesforceAPIFacade(client)
```

The Connected App must have **"Use Digital Signatures"** enabled, and the
pre-authorised user must be granted access via a Permission Set or a Profile
assignment in the app's **"Manage Profiles / Permission Sets"** section.

### Connected App setup checklist (JWT Bearer)

1. **Setup → App Manager → New Connected App**.
1. Enable **OAuth Settings** → check **Enable OAuth Settings**.
1. Set callback URL to `https://login.salesforce.com/services/oauth2/success`
   (unused in this flow, but required by Salesforce).
1. Add scopes: `api`, `refresh_token` (or `full` for broader access).
1. Check **Use Digital Signatures** → upload your public certificate (`.crt`).
1. After saving, go to **Manage → Edit Policies** → set
   **Permitted Users** to "Admin approved users are pre-authorized".
1. Assign the integration user via a Permission Set on the Connected App.

### Sandbox (JWT Bearer)

```python
token_url = "https://test.salesforce.com/services/oauth2/token"
```

The JWT `aud` claim is derived automatically from the `token_url` host, so no
other change is needed for sandbox.

### Async (JWT Bearer)

```python
from plynth.connectors.salesforce.auth import AsyncSalesforceJWTBearerAuthMiddleware
from plynth.http.transport import HttpxAsyncTransport

auth = AsyncSalesforceJWTBearerAuthMiddleware(
    client_id=os.environ["SF_CLIENT_ID"],
    username=os.environ["SF_USERNAME"],
    private_key=os.environ["SF_PRIVATE_KEY_PEM"],
    token_url="https://login.salesforce.com/services/oauth2/token",
)
transport = HttpxAsyncTransport(middlewares=[auth])
```

### Dependencies

JWT Bearer requires `PyJWT>=2.8` and `cryptography>=42`. Both are included in
the `plynth[salesforce]` extra:

```bash
pip install "plynth[salesforce]"
```

______________________________________________________________________

## Client Credentials flow

Use Client Credentials for simpler machine-to-machine setups where managing
a certificate is not desired. The `client_secret` is transmitted on every
token request, so ensure TLS is in use and rotate secrets regularly.

```python
from plynth.connectors.salesforce.auth import SalesforceClientCredentialsAuthMiddleware
from plynth.connectors.salesforce.client import SalesforceAPIClient
from plynth.connectors.salesforce.facade import SalesforceAPIFacade
from plynth.http.transport import HttpxSyncTransport

auth = SalesforceClientCredentialsAuthMiddleware(
    client_id="3MVG9...",
    client_secret="abc123",
    token_url="https://login.salesforce.com/services/oauth2/token",
)
transport = HttpxSyncTransport(middlewares=[auth])
client = SalesforceAPIClient(auth=auth, transport=transport)
sf = SalesforceAPIFacade(client)
```

The middleware fetches a token on the first request and refreshes it
automatically when it expires. The org's `instance_url` is resolved from the
token response — no manual configuration needed.

### Connected App setup checklist (Client Credentials)

1. **Setup → App Manager → New Connected App**.
1. Enable **OAuth Settings** → check **Enable Client Credentials Flow**.
1. Add scopes: `api`, `refresh_token`.
1. After saving, go to **Manage → Edit Policies** → assign a
   **Run As** user (the integration user that API calls execute as).

### Sandbox (Client Credentials)

```python
auth = SalesforceClientCredentialsAuthMiddleware(
    client_id="...",
    client_secret="...",
    token_url="https://test.salesforce.com/services/oauth2/token",
)
```

### Async (Client Credentials)

```python
from plynth.connectors.salesforce.auth import AsyncSalesforceClientCredentialsAuthMiddleware
from plynth.http.transport import HttpxAsyncTransport

auth = AsyncSalesforceClientCredentialsAuthMiddleware(
    client_id="...",
    client_secret="...",
    token_url="https://login.salesforce.com/services/oauth2/token",
)
transport = HttpxAsyncTransport(middlewares=[auth])
```

______________________________________________________________________

## Username/Password flow (legacy)

The Resource Owner Password Credentials (ROPC) flow is **deprecated** by
Salesforce and **blocked by default in all orgs created Summer '23 or later**.
Use it only for legacy orgs where neither JWT Bearer nor Client Credentials
is available.

```python
from plynth.connectors.salesforce.auth import SalesforcePasswordAuthMiddleware

auth = SalesforcePasswordAuthMiddleware(
    client_id="3MVG9...",
    client_secret="abc123",
    token_url="https://login.salesforce.com/services/oauth2/token",
    username="user@example.com",
    password="hunter2",
    security_token="XXXX",   # append to password if IP is not allowlisted
)
```

______________________________________________________________________

## Session token (edge case)

Use `SalesforceSessionAuthMiddleware` when token acquisition and refresh are
handled entirely outside Plynth (e.g. by a platform runtime or a sidecar).
Plynth only injects the bearer token and routes to the correct `instance_url`.

```python
from plynth.connectors.salesforce.auth import SalesforceSessionAuthMiddleware

auth = SalesforceSessionAuthMiddleware(
    access_token="00D...",
    instance_url="https://myorg.my.salesforce.com",
)
```

There is no token refresh. If the token expires, the next request will fail
with a 401 and Plynth will not retry with a new token.

### Async

### Async (Session token)

```python
from plynth.connectors.salesforce.auth import AsyncSalesforceSessionAuthMiddleware
```

______________________________________________________________________

## Load credentials from environment variables

Avoid hardcoding credentials. Use `SalesforceSettings` with pydantic-settings:

```python
import os
from pydantic_settings import SettingsConfigDict
from plynth.connectors.salesforce.auth import SalesforceJWTBearerAuthMiddleware
from plynth.connectors.salesforce.settings import SalesforceSettings

class MySettings(SalesforceSettings):
    model_config = SettingsConfigDict(env_prefix="SF_", env_file=".env")
    jwt_private_key: str = ""   # SF_JWT_PRIVATE_KEY

s = MySettings()
auth = SalesforceJWTBearerAuthMiddleware(
    client_id=s.client_id,
    username=s.username,
    private_key=s.jwt_private_key,
    token_url=s.token_url,
)
```

See [settings reference](../reference/settings.md) for all available fields.

______________________________________________________________________

## Choosing a flow

```text
New org (Summer '23+) or security-first?
    → JWT Bearer

Simple machine-to-machine, cert management not desired?
    → Client Credentials

Legacy org, no alternative?
    → Username/Password (deprecated)

Token managed externally?
    → Session token
```
