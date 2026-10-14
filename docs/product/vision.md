# Plynt Product Vision

Plynt is the stable foundation layer for external API integrations in Python.

The product vision is to provide a long-lived, framework-agnostic client
architecture that teams can adopt once and evolve safely over time.

______________________________________________________________________

## North Star

Teams should be able to build and operate external API integrations with:

- predictable behavior,
- explicit configuration,
- strong typing,
- sync and async parity,
- and minimal framework lock-in.

______________________________________________________________________

## Strategic Goals

1. Keep the core package minimal and framework-independent.
1. Preserve architecture consistency through ADR-driven decisions.
1. Maintain high confidence releases with strict quality gates.
1. Validate the core through real connector implementations.
1. Keep connector extraction possible without redesigning core abstractions.

______________________________________________________________________

## Current Scope

- Core transport, middleware, settings, retry, auth, and error abstractions.
- HTTP implementation based on httpx2.
- Salesforce connector as the primary real-world validation connector.
- Optional async-first gRPC foundation and experimental Salesforce CDC.
- Generic LLM connector with OpenAI and Anthropic provider adapters.
- Optional Django, DRF, and FastAPI framework adapters.

HTTP capabilities preserve sync/async parity. The initial gRPC and CDC
scope is async-only under ADR-0030 and SF-0013.

The current delivery focus is hardening an experimental candidate, not
expanding capabilities or claiming production-ready Salesforce eventing.
See the [roadmap](roadmap.md) and
[hardening evidence](../releases/2026-10-13-experimental-rc-hardening-evidence.md)
for implemented scope and remaining acceptance work.

______________________________________________________________________

## Non-Goals

- Becoming a web framework.
- Embedding business-specific workflows in generic connectors.
- Adding optional dependencies to core without clear architectural need.

______________________________________________________________________

## Success Signals

- Stable and documented public API evolution toward 1.0.
- Green quality gate on every release path.
- New connector capabilities added without breaking core boundaries.
- Clear, auditable decisions in ADRs for all architectural changes.
