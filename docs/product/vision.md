# Plynth Product Vision

Plynth is the stable foundation layer for external API integrations in Python.

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
- HTTP implementation based on httpx.
- Salesforce connector as the primary real-world validation connector.

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
