# ADR-0039: Typed Transport and Authentication Errors

**Date:** 2026-11-01
**Status:** Proposed

## Context

Consumers must import `httpx2` to handle network failures. The httpx2
transports let timeouts, connect errors, and pool exhaustion propagate
unchanged, although `plynt.base.errors.TransportError` exists. This leaks
the backend through the transport abstraction and couples application code
to one HTTP library.

Token endpoint failures in the OAuth2 and Salesforce auth middleware raise
a plain `RuntimeError` whose message includes the raw response body. That
body can contain error descriptions or echoed credentials, and the message
ends up in logs and error trackers.

[ADR-0038](0038-http-retry-exceptions-and-stream-ownership.md) rejected
normalizing transport exceptions because it changes observable exception
types and the behavior of custom retry classifiers. Roadmap item 2o asks
for that normalization. This record revisits that alternative explicitly.

## Decision

Proposed:

1. Add two protocol-agnostic subclasses of `TransportError` in
   `plynt.base.errors`:
   - `TransportTimeoutError` for connect, read, write, and pool timeouts.
   - `TransportConnectionError` for connect, network, proxy, and remote
     protocol failures.
1. The httpx2 sync and async transports wrap those backend exceptions in
   the new types and keep the original exception as `__cause__`.
   Local protocol errors and programming errors are not wrapped.
1. Add `AuthenticationError(TransportError)` in `plynt.base.errors` with a
   `status_code` attribute. OAuth2 and Salesforce token flows raise it for
   non-success token responses. The message contains the status code only,
   never the response body. The body stays available as an attribute that
   is excluded from `str()` and `repr()`.
1. Keep `RuntimeError` as an additional base of `AuthenticationError`, so
   existing `except RuntimeError` handlers keep working during 0.x.
1. The default retry classifier recognizes the new plynt types. It keeps
   recognizing raw httpx2 exceptions for custom transports, so ADR-0038's
   rule that core policies never import the backend stays intact.
1. Changing the raised network exception types is a breaking change.
   Ship it with a breaking Conventional Commit and a migration note per
   [ADR-0035](0035-pre-1-versioning-policy.md).

This supersedes the "Normalize exceptions in the transport" rejection in
ADR-0038. ADR-0038's stream ownership decisions remain unchanged.

## Alternatives Considered

### Keep raw backend exceptions (status quo)

No breaking change, but consumers stay coupled to httpx2 and the token
body keeps leaking into messages. Rejected.

### Dual inheritance from plynt and httpx2 exception types

Subclasses inheriting from both `TransportTimeoutError` and
`httpx2.TimeoutException` would keep old `except` clauses working. It
depends on httpx2 constructor internals and makes the backend part of the
public error hierarchy. Rejected.

### Map network failures to HTTP status errors

Treating a timeout as `RequestTimeoutError` (408) mixes transport failures
with server responses. Status errors require a status code. Rejected.

## Rationale

Typed errors complete the existing `TransportError` hierarchy and let
applications, framework adapters, and error trackers handle failures
without backend imports. Keeping `__cause__` preserves full diagnostics.
The pre-1.0 policy allows the break; the `RuntimeError` base limits
impact on the auth path, where most existing handlers catch broadly.

## Consequences

### Positive

- Applications handle timeouts and connection failures with plynt types.
- Token response bodies no longer reach logs through exception messages.
- Framework adapters can map transport failures to 502 or 504 responses.

### Negative / Tradeoffs

- `except httpx2.TimeoutException` and similar handlers stop matching.
- Custom retry classifiers keyed on httpx2 types must add plynt types.

### Risks

- Missing a backend exception class leaves some failures unwrapped.
  Mitigation: parametrized tests per mapped httpx2 exception, sync and
  async, plus a test that unmapped exceptions propagate unchanged.

## Related ADRs

- [ADR-0006](0006-transport-layer.md): transport layer.
- [ADR-0011](0011-authentication.md): authentication.
- [ADR-0012](0012-retry-strategy.md): retry strategy.
- [ADR-0023](0023-httpx2-transport-backend.md): HTTP backend.
- [ADR-0035](0035-pre-1-versioning-policy.md): pre-1.0 breaking releases.
- [ADR-0038](0038-http-retry-exceptions-and-stream-ownership.md):
  partially superseded.
