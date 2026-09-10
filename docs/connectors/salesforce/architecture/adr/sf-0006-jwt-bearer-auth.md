# SF-0006 — JWT Bearer Authentication Flow

**Status:** Accepted
**Date:** 2026-05-08
**Scope:** `plynth.http.middleware.auth`, `plynth.connectors.salesforce`

______________________________________________________________________

## Context

The Salesforce OAuth2 JWT Bearer flow is the recommended server-to-server
authentication method. It differs from Client Credentials in one important
way: the client proves its identity by signing a short-lived JWT assertion
with a private key rather than transmitting a shared secret. Salesforce
verifies the signature against a certificate registered in the connected app
or external client app.

From Summer '23, the Username-Password flow is blocked by default in all
newly created Salesforce orgs. The JWT Bearer flow is the primary alternative
for automated integrations where interactive login is not possible.

The existing `OAuth2AuthMiddlewareBase` in `plynth.http.middleware.auth`
already provides token lifecycle management (caching, lock,
401-invalidate-retry). JWT Bearer is specified generically in RFC 7523 and is
not Salesforce-specific, so the shared OAuth2 package is the right home for
the flow mechanics.

______________________________________________________________________

## Decision

### 1. Add generic RFC 7523 middleware in plynth core

`OAuth2JWTBearerMiddleware` and `AsyncOAuth2JWTBearerMiddleware` are added to
`plynth.http.middleware.auth.oauth2`. They implement RFC 7523 token request
shape and reuse the existing OAuth2 token lifecycle from the base classes.

To keep core dependency-light, JWT signing is delegated to an
`assertion_factory` callback. Core does not import JWT libraries.

`SalesforceJWTBearerAuthMiddleware` and its async counterpart now extend these
generic JWT classes, while still reusing `_SalesforceInstanceUrlSyncMixin` /
`_SalesforceInstanceUrlAsyncMixin` for `instance_url` extraction.

### 2. Salesforce JWT assertion construction

Each call to Salesforce `assertion_factory` constructs a fresh signed JWT with:

| Claim | Value                                                                        |
| ----- | ---------------------------------------------------------------------------- |
| `iss` | `client_id` (consumer key of the connected/external app)                     |
| `sub` | `username` (Salesforce username to impersonate)                              |
| `aud` | scheme + host derived from `token_url` (e.g. `https://login.salesforce.com`) |
| `exp` | `now + jwt_exp_seconds` (default 180 s; hard cap 300 s per Salesforce limit) |

Algorithm: **RS256** (RSA + SHA-256). The private key must be provided as a
PEM-encoded string or bytes.

The generic core middleware sends the token request body as:

```text
grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer
assertion=<signed_jwt>
```

### 3. Sandbox support

Sandbox orgs use `https://test.salesforce.com` as the login host. Because
`aud` is derived from `token_url`, callers point `token_url` at the sandbox
endpoint and `aud` is set correctly automatically:

```python
# Production
token_url = "https://login.salesforce.com/services/oauth2/token"
# Sandbox
token_url = "https://test.salesforce.com/services/oauth2/token"
```

### 4. Dependency

Salesforce JWT signing requires `PyJWT>=2.12.1` and `cryptography>=50.0.1`.
This remains connector-scoped via optional extra `plynth[salesforce]`:

```toml
[project.optional-dependencies]
salesforce = ["httpx2>=2.5.0", "PyJWT>=2.12.1", "cryptography>=50.0.1"]
```

`PyJWT` and `cryptography` are not added to the `httpx2` backend extra because JWT
signing is connector-level behavior. A lazy import with a clear
`ImportError` message guards the Salesforce code path.

### 5. Cache key

```text
plynth:oauth2:sha256("jwt:<token_url>:<client_id>:<username>")
```

This is consistent with the existing Client Credentials and Password cache
key patterns and correctly separates tokens for different orgs or users.

______________________________________________________________________

## Consequences

- Generic RFC 7523 middleware is now available in `plynth.http.middleware.auth`.
- Callers who need JWT Bearer must install `plynth[salesforce]`.
- The private key is held in memory for the lifetime of the middleware
  instance; callers are responsible for loading it securely (e.g. from an
  environment variable or secret manager).
- `jwt_exp_seconds` is validated at construction time: values above 300 or
  below 1 raise `ValueError` to prevent Salesforce rejections at runtime.
- Username-Password middleware is retained for legacy orgs but receives no
  new features (see ROADMAP).
