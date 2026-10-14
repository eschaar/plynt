# Settings reference

Plynt uses a three-layer settings hierarchy built on `pydantic-settings`.
Each layer extends the previous one.

```text
Settings          (plynt.base.settings)
└── HTTPSettings  (plynt.http.settings)
    └── ApiSettings
```

## Settings (base)

**Module:** `plynt.base.settings`

| Field   | Type   | Default | Description       |
| ------- | ------ | ------- | ----------------- |
| `debug` | `bool` | `False` | Enable debug mode |

Reads from `.env` by default. Override `model_config` in a subclass to
set a custom env prefix, env file, or other pydantic-settings options.

______________________________________________________________________

## HTTPSettings

**Module:** `plynt.http.settings`

Extends `Settings` with all fields needed to build an HTTP transport.

### Fields

| Field             | Type                             | Default | Description                                                                     |
| ----------------- | -------------------------------- | ------- | ------------------------------------------------------------------------------- |
| `base_url`        | `str`                            | `""`    | Base URL of the external service                                                |
| `timeout_connect` | `float \| None`                  | `5.0`   | TCP connect timeout in seconds                                                  |
| `timeout_read`    | `float \| None`                  | `30.0`  | Response read timeout in seconds                                                |
| `timeout_write`   | `float \| None`                  | `10.0`  | Request write timeout in seconds                                                |
| `timeout_pool`    | `float \| None`                  | `10.0`  | Connection pool wait timeout in seconds                                         |
| `max_attempts`    | `int`                            | `3`     | Total request attempts (used when `retry` is `None`)                            |
| `proxy`           | `str \| None`                    | `None`  | Proxy URL                                                                       |
| `verify`          | `bool \| str`                    | `True`  | TLS verification — `True` (system CAs), `False` (disable), or path to CA bundle |
| `cert`            | `tuple[str, str] \| str \| None` | `None`  | Client certificate — PEM path or `(cert_path, key_path)` tuple                  |

### Properties (override in subclasses)

| Property             | Returns                          | Default | Description                                                                                |
| -------------------- | -------------------------------- | ------- | ------------------------------------------------------------------------------------------ |
| `auth`               | `AuthConfig \| None`             | `None`  | Auth configuration — see [Auth configs reference](auth-configs.md)                         |
| `retry`              | `HttpRetryPolicy \| None`        | `None`  | Retry policy — falls back to `HttpRetryPolicy(max_attempts=self.max_attempts)` when `None` |
| `caches`             | `dict[str, CacheConfig] \| None` | `None`  | Named cache configurations                                                                 |
| `default_cache`      | `str \| None`                    | `None`  | Name of the cache to use for HTTP response caching                                         |
| `default_auth_cache` | `str \| None`                    | `None`  | Name of the cache to use for OAuth2 token caching                                          |

### Default env prefix

`PLYNT_` — override in a subclass via `model_config`:

```python
from pydantic_settings import SettingsConfigDict
from plynt.http.settings import HTTPSettings


class MySettings(HTTPSettings):
    model_config = SettingsConfigDict(
        env_prefix="MY_SERVICE_",
        env_file=".env",
    )
```

### Build a transport from settings

```python
from plynt.http.transport import HttpxSyncTransport

settings = MySettings()
transport = HttpxSyncTransport.from_settings(settings)
```

`from_settings()` wires auth, retry policy, and cache from the settings
object automatically.

### Example — full subclass

```python
from plynt.http.auth import OAuth2ClientCredentialsConfig
from plynt.http.policies import HttpRetryPolicy
from plynt.http.settings import HTTPSettings
from pydantic_settings import SettingsConfigDict


class OrderServiceSettings(HTTPSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORDER_",
        env_file=".env",
    )

    client_id: str = ""
    client_secret: str = ""

    @property
    def auth(self):
        if not self.client_id:
            return None
        return OAuth2ClientCredentialsConfig(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_url="https://auth.example.com/token",
        )

    @property
    def retry(self):
        return HttpRetryPolicy(max_attempts=5, backoff_initial=1.0)
```

______________________________________________________________________

## ApiSettings

**Module:** `plynt.http.settings`

Thin subclass of `HTTPSettings`. Signals that the service uses a REST API
rather than arbitrary HTTP. No additional fields.

```python
from plynt.http.settings import ApiSettings


class MyApiSettings(ApiSettings):
    model_config = SettingsConfigDict(env_prefix="MY_")
    base_url: str = "https://api.example.com"
```

______________________________________________________________________

## Environment variables

All `HTTPSettings` fields map to env vars under the configured prefix.
For example, with `env_prefix="MY_"`:

| Env var              | Field             |
| -------------------- | ----------------- |
| `MY_BASE_URL`        | `base_url`        |
| `MY_TIMEOUT_CONNECT` | `timeout_connect` |
| `MY_TIMEOUT_READ`    | `timeout_read`    |
| `MY_MAX_ATTEMPTS`    | `max_attempts`    |
| `MY_PROXY`           | `proxy`           |
| `MY_VERIFY`          | `verify`          |
