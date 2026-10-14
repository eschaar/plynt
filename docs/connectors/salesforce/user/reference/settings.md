# Settings reference: `SalesforceSettings`

`SalesforceSettings` extends `ApiSettings` (from `plynt.base.settings`) with
Salesforce-specific configuration fields.

## Fields

| Field            | Type  | Default | Description                                                                                                                                                                                                                                        |
| ---------------- | ----- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `instance_url`   | `str` | `""`    | Org-specific Salesforce host — e.g. `https://myorg.my.salesforce.com`. Not required when using `SalesforceAPIClient` with the Client Credentials middleware (it is resolved from the token response). Provide only when using a plain `APIClient`. |
| `api_version`    | `str` | `""`    | REST API version to target, e.g. `"62.0"`. When empty (default), services resolve the latest version lazily from `GET /services/data/`.                                                                                                            |
| `client_id`      | `str` | `""`    | OAuth2 client (consumer) key from the Connected App.                                                                                                                                                                                               |
| `client_secret`  | `str` | `""`    | OAuth2 client (consumer) secret from the Connected App.                                                                                                                                                                                            |
| `token_url`      | `str` | `""`    | Full OAuth2 token endpoint URL. Use `https://login.salesforce.com/services/oauth2/token` for production and `https://test.salesforce.com/services/oauth2/token` for sandboxes.                                                                     |
| `username`       | `str` | `""`    | Salesforce username. Required only for the Username/Password flow.                                                                                                                                                                                 |
| `password`       | `str` | `""`    | Salesforce password. Required only for the Username/Password flow.                                                                                                                                                                                 |
| `security_token` | `str` | `""`    | Security token appended to the password for orgs without IP allowlisting. Leave empty when IP ranges are allowlisted.                                                                                                                              |

## Load from environment variables

Use `pydantic-settings` to read credentials from the environment:

```python
from pydantic_settings import SettingsConfigDict
from plynt.connectors.salesforce.settings import SalesforceSettings


class MySettings(SalesforceSettings):
    model_config = SettingsConfigDict(env_prefix="SF_", env_file=".env")


s = MySettings()
```

With `env_prefix="SF_"`, the environment variable names become:

| Field            | Environment variable |
| ---------------- | -------------------- |
| `instance_url`   | `SF_INSTANCE_URL`    |
| `api_version`    | `SF_API_VERSION`     |
| `client_id`      | `SF_CLIENT_ID`       |
| `client_secret`  | `SF_CLIENT_SECRET`   |
| `token_url`      | `SF_TOKEN_URL`       |
| `username`       | `SF_USERNAME`        |
| `password`       | `SF_PASSWORD`        |
| `security_token` | `SF_SECURITY_TOKEN`  |

## Pass settings to the auth middleware

```python
from plynt.connectors.salesforce.auth import SalesforceClientCredentialsAuthMiddleware

auth = SalesforceClientCredentialsAuthMiddleware(
    client_id=s.client_id,
    client_secret=s.client_secret,
    token_url=s.token_url,
)
```
