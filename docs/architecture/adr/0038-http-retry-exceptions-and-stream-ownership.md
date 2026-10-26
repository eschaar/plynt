# ADR-0038: HTTP Retry Exceptions and Stream Ownership

**Date:** 2026-10-26
**Status:** Accepted

## Context

The default retry classifier recognizes built-in network exceptions, but
httpx2 raises its own exception classes. Configured HTTP retries therefore
do not retry backend connection failures.

Status retries and OAuth2 re-authentication can also discard open streaming
responses. The caller cannot close a response that middleware never returns.
Both defects affect synchronous and asynchronous requests.

## Decision

Extend the default exception classifier of `HttpRetryPolicy` in the HTTP
layer to recognize httpx2 timeouts, network errors, remote protocol errors,
and proxy errors, alongside the existing built-in network exceptions.
Local protocol errors, unsupported protocols, and programming errors are
not transient network failures.

This refines ADR-0012: HTTP policies may recognize optional backend
exceptions, but remain importable without the backend installed. Core
policies and middleware must not import HTTP backend libraries. Explicit
caller-supplied classifiers replace the default and remain authoritative.
Exceptions keep their original types; no transport exception remapping
or new runtime dependency is introduced.

Middleware owns a streaming response it discards before retrying.
Retry and OAuth2 middleware must close such responses before waiting,
refreshing credentials, or issuing another request. Cleanup failures
propagate rather than silently leaking resources. The final response,
including an exhausted retryable response, remains caller-owned.

No middleware consumes or restarts a body after returning a stream.
Sync and async paths use the existing response lifecycle methods.

## Alternatives Considered

### Normalize exceptions in the transport

This would make core classifiers work unchanged, but changes externally
observable exception types and custom classifier behavior. Rejected.

### Import the backend in core policies

This is simple but violates the optional HTTP boundary. Rejected.

### Require every caller to configure classification and cleanup

This preserves the defects in default HTTP behavior. Callers also cannot
clean up discarded responses that are never returned to them. Rejected.

## Rationale

HTTP-specific classification fixes the backend mismatch at the existing
policy extension point. Explicit ownership prevents resource leaks without
changing public interfaces, retry limits, or the streaming execution model.

## Consequences

- Opt-in HTTP retries handle backend network failures as documented.
- Custom classifiers and network-retry opt-out remain unchanged.
- Discarded streams release resources before the next attempt.
- Existing retry safety considerations still apply to non-idempotent calls.
- Backend exception classification requires targeted regression tests.
- Tests must cover cleanup ordering, exhausted retries, and cleanup failures.

## Related ADRs

- [ADR-0012: Retry Strategy](0012-retry-strategy.md)
- [ADR-0017: Streaming Response Support](0017-streaming-response.md)
- [ADR-0023: HTTP Transport Backend](0023-httpx2-transport-backend.md)
