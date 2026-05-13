# ADR-0011: Authentication

## Status

Accepted

## Implementation Notes

**Implemented:** `SyncMiddleware` / `AsyncMiddleware` protocol
(`plynth.base.middleware`); `BearerTokenAuthMiddleware`, `BasicAuthMiddleware`,
`OAuth2AuthMiddlewareBase`, `OAuth2ClientCredentialsMiddleware`,
`OAuth2PasswordMiddleware`, `OAuth2AuthMiddleware` (alias);
async counterparts (`AsyncBearerTokenAuthMiddleware`, etc.) in
`plynth.http.middleware.auth`.

**Implemented:** Typed auth configuration: `BearerAuthConfig`,
`BasicAuthConfig`, `OAuth2ClientCredentialsConfig`, `OAuth2PasswordConfig`,
`AuthConfig` type alias, `auth_from_config()`, `async_auth_from_config()` in
`plynth.http.auth`.

**Removed:** Flat credential fields (`bearer_token`, `client_id`,
`client_secret`, `token_url`, `auth_max_attempts`, `basic_username`,
`basic_password`) from `HTTPSettings`. Replaced by the `auth` property.

**Removed:** `Authenticator` / `AsyncAuthenticator` protocols
(`plynth.core.auth`); `authenticator=` parameter on `BaseSyncTransport` /
`BaseAsyncTransport`.

## Context

Plynth is a framework-agnostic API client library. Many external APIs require
authentication — most commonly OAuth2 client credentials or bearer tokens,
but also API keys, Basic Auth, and custom schemes.

Authentication in an HTTP client library involves several interacting concerns:

1. **Obtaining credentials** — calling a token endpoint before a request.
1. **Attaching credentials** — adding headers (e.g. `Authorization: Bearer …`).
1. **Token caching** — avoiding unnecessary token endpoint calls when the
   current token is still valid, using a TTL.
1. **Proactive refresh** — refreshing a token before it expires.
1. **Reactive re-authentication** — retrying the original request after
   re-authenticating when a `401 Unauthorized` is received.
1. **Retry limits** — bounding the number of re-authentication attempts.

These concerns must not be embedded in the Client Layer (ADR-0008), which
explicitly excludes authentication. They also must not produce a framework
dependency in core.

The earlier approach exposed flat credential fields on `HTTPSettings` and used
an implicit priority chain in `from_settings()` to decide which auth middleware
to wire. This caused several problems:

1. **Implicit selection.** The active auth method is determined by which fields
   happen to be set, making accidental misconfigurations hard to detect.
1. **No structured options.** OAuth2 `ttl_leeway` and `max_retries` had no
   exposure in settings; they silently used defaults.
1. **Type mixing.** A single flat namespace held mutually exclusive fields.
1. **No construction-time validation.** An incomplete config was silently
   ignored rather than failing fast.
1. **Inconsistency with ADR-0010.** Cache backends switched to a typed config
   pattern; auth remained on the legacy implicit approach.

## Decision

### Auth Is a Transport Middleware Concern

Authentication is implemented as **transport-layer middleware** — concrete
implementations of `SyncMiddleware` / `AsyncMiddleware` (ADR-0013). Auth
middleware is an explicit, ordered entry in the `middlewares` list passed to
`BaseSyncTransport` / `BaseAsyncTransport`.

This replaces the previous design where a separate `Authenticator` protocol
and a dedicated `authenticator=` constructor parameter handled auth inside
`_dispatch_request`. The middleware model:

- Eliminates a parallel mechanism alongside `middlewares`.
- Makes auth ordering explicit and user-controlled.
- Gives auth middleware full access to both request and response, enabling
  reactive re-authentication on 401 naturally within `handle()`.
- Removes the need for `_AsyncAuthAdapter` bridge classes.

### Canonical Middleware Ordering

```python
middlewares = [
    CacheMiddleware(...),           # outermost: cache hit skips auth + I/O
    BearerTokenAuthMiddleware(...), # or OAuth2AuthMiddleware / BasicAuthMiddleware
    RetryMiddleware(policy),        # innermost above network I/O
]
```

### Auth Middleware Directory: `plynth.http.middleware.auth/`

```text
plynth/http/middleware/auth/
    __init__.py     # re-exports all classes
    bearer.py       # BearerTokenAuthMiddleware, AsyncBearerTokenAuthMiddleware
    basic.py        # BasicAuthMiddleware, AsyncBasicAuthMiddleware
    oauth2.py       # OAuth2 base classes and concrete flow implementations
```

### Auth Middleware Implementations

Sync bearer and basic (no 401 retry):

```python
class BearerTokenAuthMiddleware(SyncMiddleware): ...
class BasicAuthMiddleware(SyncMiddleware): ...
```

Bearer and Basic auth do not implement 401 retry — a 401 with static
credentials indicates a configuration error, not a transient failure.

Sync OAuth2 — abstract base and concrete flows:

```python
class OAuth2AuthMiddlewareBase(SyncMiddleware, ABC):
    """Abstract base; handles token lifecycle, 401-retry, and invalidation."""

class OAuth2ClientCredentialsMiddleware(OAuth2AuthMiddlewareBase):
    """Client Credentials flow (grant_type=client_credentials)."""

class OAuth2PasswordMiddleware(OAuth2AuthMiddlewareBase):
    """Resource Owner Password Credentials flow (grant_type=password).
    Legacy; avoid for new integrations."""

OAuth2AuthMiddleware = OAuth2ClientCredentialsMiddleware  # backward alias
```

Async mirrors follow the same hierarchy, prefixed `Async`.

### Reactive 401 Handling in OAuth2 Middleware

```python
def handle(self, request, next_handler):
    request.headers.update(self._get_token_header())   # lazy fetch + cache
    response = next_handler(request)                   # → Retry → I/O
    if response.status_code == 401:
        self._invalidate()                             # discard stale token
        request.headers.update(self._get_token_header())  # re-fetch
        response = next_handler(request)               # one retry
    return response
```

### Token Caching in OAuth2 Middleware

Token caching uses the `CacheBackend` protocol from `plynth.base.cache`
(ADR-0010). Each OAuth2 middleware instance stores `(token, expires_at)`
tuples in the backend.

- Default backend: `LocMemCache()` created per-instance (in-process,
  thread-safe).
- Shared backend: pass any `CacheBackend` via `token_cache=` to share tokens
  across instances or processes (e.g. `RedisCache` for distributed caching).
- `ttl_leeway` seconds are subtracted from `expires_in` to avoid using a
  nearly-expired token.
- `asyncio.Lock` (async) / `threading.Lock` (sync) ensures only one coroutine
  or thread fetches at a time when the cache is empty or expired.

### Typed Auth Configuration Pattern

Auth mechanism is made explicit through typed configuration dataclasses in
`plynth.http.auth`:

```python
@dataclass
class BearerAuthConfig:
    token: str

@dataclass
class BasicAuthConfig:
    username: str
    password: str

@dataclass
class OAuth2ClientCredentialsConfig:
    client_id: str
    client_secret: str
    token_url: str
    max_retries: int = 2
    ttl_leeway: int = 30

@dataclass
class OAuth2JWTBearerConfig:
    token_url: str
    assertion_factory: Callable[[], str]
    cache_key_material: str
    scope: str | None = None
    max_retries: int = 2
    ttl_leeway: int = 30

@dataclass
class OAuth2PasswordConfig:
    client_id: str
    client_secret: str
    token_url: str
    username: str
    password: str
    max_retries: int = 2
    ttl_leeway: int = 30
```

The union type alias
`AuthConfig = BearerAuthConfig | BasicAuthConfig | OAuth2ClientCredentialsConfig | OAuth2JWTBearerConfig | OAuth2PasswordConfig`
replaces the implicit field-presence mechanism.

### Factory Functions

```python
def auth_from_config(
    config: AuthConfig,
    token_cache: CacheBackend | None = None,
) -> SyncMiddleware: ...

def async_auth_from_config(
    config: AuthConfig,
    token_cache: CacheBackend | None = None,
) -> AsyncMiddleware: ...
```

Both dispatch on the concrete config type and construct the appropriate
middleware. The `token_cache` parameter is kept separate from the config
object — it is a runtime object (wired via `settings.caches` and
`settings.default_auth_cache`, per ADR-0010) and must not live in a
serialisable config dataclass.

### Settings API

`HTTPSettings` loses all flat auth fields and gains one `@property`:

```python
@property
def auth(self) -> AuthConfig | None:
    return None  # override in subclass to enable auth
```

### Subclass Usage

Credential values remain as plain pydantic env-var fields on the settings
subclass; the `auth` property assembles them into an `AuthConfig` object:

```python
from plynth.http.auth import OAuth2ClientCredentialsConfig
from plynth.http.settings import HTTPSettings

class MySettings(HTTPSettings):
    client_id:     str = ""  # MY_CLIENT_ID=...
    client_secret: str = ""  # MY_CLIENT_SECRET=...

    @property
    def auth(self) -> AuthConfig | None:
        if not self.client_id:
            return None
        return OAuth2ClientCredentialsConfig(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_url="https://auth.example.com/token",
            ttl_leeway=60,
        )
```

### `from_settings()` Logic

The implicit priority chain is eliminated. A single explicit config object
determines the auth middleware:

```python
auth_config = settings.auth
if auth_config is not None:
    auth_token_cache = (
        cache_from_config(caches[settings.default_auth_cache])
        if caches and settings.default_auth_cache
            and settings.default_auth_cache in caches
        else None
    )
    middlewares.append(auth_from_config(auth_config, token_cache=auth_token_cache))
```

### No `Authenticator` Protocol in Core

`plynth.core.auth` is retired. Auth is middleware, not a separate protocol.

## Consequences

- Auth mechanism is explicit and impossible to misread from the settings
  object.
- All OAuth2 options (`max_retries`, `ttl_leeway`) are typed named fields with
  IDE auto-complete and static type checking.
- Construction-time validation via `@dataclass` field requirements — missing
  required fields are caught when the config object is created.
- `from_settings()` has no auth-specific business logic; all wiring is in the
  `auth_from_config()` factory.
- Auth and retry are both explicit, visible, ordered middleware entries.
- `401` reactive re-auth happens inside `OAuth2AuthMiddleware.handle()`, at
  most once per request, without touching the outer middleware layers.
- Bearer and Basic auth never retry on 401 — fail-fast by design.
- Consistent with ADR-0010 (typed cache config).

## Related

- ADR-0003 — Dependency Policy
- ADR-0004 — Settings and Configuration
- ADR-0006 — Transport Layer
- ADR-0008 — Client Layer
- ADR-0010 — Caching (token cache backend)
- ADR-0013 — Transport Base Class (middleware chain)
