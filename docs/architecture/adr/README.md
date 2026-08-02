# Architecture ADR Index

This index lists architecture decision records (ADRs) for plynth.

## Status Summary

- Accepted: 30
- Proposed: 0

## ADR List

<!-- markdownlint-disable MD060 -->

| ADR                                                                 | Title                                             | Status   |
| ------------------------------------------------------------------- | ------------------------------------------------- | -------- |
| [ADR-0001](0001-architecture-principles.md)                         | Architecture Principles                           | Accepted |
| [ADR-0002](0002-layered-architecture.md)                            | Layered Architecture                              | Accepted |
| [ADR-0003](0003-dependency-policy.md)                               | Dependency Policy                                 | Accepted |
| [ADR-0004](0004-settings-and-configuration.md)                      | Settings and Configuration                        | Accepted |
| [ADR-0005](0005-request-layer.md)                                   | Request Layer                                     | Accepted |
| [ADR-0006](0006-transport-layer.md)                                 | Transport Layer                                   | Accepted |
| [ADR-0007](0007-response-layer.md)                                  | Response Layer                                    | Accepted |
| [ADR-0008](0008-client-layer.md)                                    | Client Layer                                      | Accepted |
| [ADR-0009](0009-service-layer.md)                                   | Service Layer                                     | Accepted |
| [ADR-0010](0010-caching.md)                                         | Caching                                           | Accepted |
| [ADR-0011](0011-authentication.md)                                  | Authentication                                    | Accepted |
| [ADR-0012](0012-retry-strategy.md)                                  | Retry Strategy                                    | Accepted |
| [ADR-0013](0013-transport-base-class.md)                            | Transport Base Class                              | Accepted |
| [ADR-0014](0014-logging.md)                                         | Logging Strategy                                  | Accepted |
| [ADR-0015](0015-header-middleware.md)                               | Header Middleware                                 | Accepted |
| [ADR-0016](0016-vcr-testsupport.md)                                 | VCR Testsupport Layer                             | Accepted |
| [ADR-0017](0017-streaming-response.md)                              | Streaming Response Support                        | Accepted |
| [ADR-0018](0018-raw-response-access.md)                             | Raw Response Access                               | Accepted |
| [ADR-0019](0019-circuit-breaker-middleware.md)                      | Circuit Breaker Middleware                        | Accepted |
| [ADR-0020](0020-rate-limit-middleware.md)                           | Rate Limit Middleware                             | Accepted |
| [ADR-0021](0021-llm-contract-boundary.md)                           | Generic LLM Contract                              | Accepted |
| [ADR-0022](0022-upstream-rate-governance.md)                        | Upstream Rate Governance                          | Accepted |
| [ADR-0023](0023-httpx2-transport-backend.md)                        | HTTP Transport Backend Migration to httpx2        | Accepted |
| [ADR-0024](0024-framework-adapter-strategy.md)                      | Framework Adapter Strategy                        | Accepted |
| [ADR-0025](0025-django-adapter-sync-async-strategy.md)              | Django Adapter Sync and Async Strategy            | Accepted |
| [ADR-0026](0026-fastapi-adapter-lifecycle-and-di.md)                | FastAPI Adapter Lifecycle and Dependency Strategy | Accepted |
| [ADR-0027](0027-public-api-compatibility-and-deprecation-policy.md) | Public API Compatibility and Deprecation Policy   | Accepted |
| [ADR-0028](0028-supported-environments-and-extras-policy.md)        | Supported Environments and Extras Policy          | Accepted |
| [ADR-0029](0029-release-acceptance-gates-and-evidence-model.md)     | Release Acceptance Gates and Evidence Model       | Accepted |
| [ADR-0030](0030-grpc-protocol-boundary.md)                          | Generic gRPC Protocol Boundary and Scope          | Accepted |

<!-- markdownlint-enable MD060 -->

## When to Add a New ADR

Add an ADR for changes that affect:

- public API surface or behavioral contracts,
- package boundaries or dependency model,
- core abstractions, layering, or sync/async strategy,
- middleware execution semantics,
- installation extras or optional-framework strategy.

Use the next sequential number (currently: `0031`).
