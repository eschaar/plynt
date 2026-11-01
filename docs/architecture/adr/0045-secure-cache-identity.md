# ADR-0045: Secure Cache Identity and Reuse

## Status

Accepted

## Context

ADR-0010 defines deterministic HTTP response cache keys but excludes request
headers that can affect a response. Query values may also be ambiguous when
encoded as scalar representations. OAuth2 token cache identity must include
all request parameters that affect the token grant.

The shared response cache must not reuse responses whose cache directives or
`Vary` semantics cannot safely be honored. Cache middleware can only include
headers added before its position in the middleware chain, so its placement
must account for request-mutating middleware such as authentication.

## Decision

### Response Cache Identity

- Build a versioned cache-key representation and SHA-256 hash it. The version
  prevents lookup of entries produced by earlier key formats.
- Include the HTTP method, URL, query parameters, and every request header
  present at the cache middleware boundary. Normalize header names to
  lowercase and sort headers and query parameter names deterministically.
- Encode query values with `urlencode(..., doseq=True)` so multi-valued
  parameters are represented as repeated encoded values rather than Python
  object representations.
- Never expose raw header values, including credentials, in keys or logs.
- Place response cache middleware after middleware that adds or changes
  outbound request headers, including authentication middleware. This makes
  the key reflect the headers sent to the transport. Cache hits may therefore
  perform authentication work before the cache lookup.

### Cache-Control and Vary

- A request with `Cache-Control: no-store` or `no-cache` bypasses both lookup
  and storage because this middleware does not implement revalidation.
- Do not store a response with `Cache-Control: no-store`, `private`, or
  `no-cache`; the configured backend may be shared and revalidation is not
  implemented.
- Do not store a response with `Vary: *` or malformed `Vary` fields.
  Valid `Vary` field names are supported because all request headers are
  included in the cache identity.

### OAuth2 Token Cache Identity

Include the scope in the sync and async JWT bearer OAuth2 token cache
identities whenever scope is sent in the token request. Scope-distinct
requests must not share a token entry; requests with the same scope may reuse
one. Continue hashing key material before using it as a backend key.

### Dependency and Compatibility Boundaries

No new runtime dependencies, frameworks, or core abstractions are introduced.
Changed HTTP response key formats intentionally make prior response-cache
entries unreachable; reduced cache hit rates during migration are accepted.

## Consequences

- Request representations differing in headers or query values do not
  accidentally share response cache entries.
- Some responses and requests that were previously cached are bypassed,
  reducing hit rates in exchange for safe reuse semantics.
- Authentication runs before response-cache lookup where it can change
  outbound headers.
- Existing response-cache entries are not reused after the key format change.

## Related

- ADR-0003 — Dependency Policy
- ADR-0010 — Caching
- ADR-0011 — Authentication
- ADR-0013 — Transport Base Class
