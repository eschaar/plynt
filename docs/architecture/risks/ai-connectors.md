# AI Connector Boundary Risk Note

## Why this document exists

This note captures architecture risks at the boundary between:

- Salesforce AI services in the Salesforce connector
- the planned generic LLM connector

The goal is to prevent coupling and rework while both tracks evolve.

## Correct placement

This is an architecture risk note, not a product work item.

- It does not define feature scope or delivery order.
- It defines boundary risks and mitigation rules across connectors.

Because the scope is cross-connector, it belongs in generic architecture docs,
not only in Salesforce docs.

## Scope

- Contract boundary between connector-local and generic AI models
- Dependency and layering boundaries between connectors
- Streaming error semantics across client and service layers

## High-severity risks

1. Contract divergence between Salesforce AI and generic LLM models
   can cause incompatible abstractions and expensive rework.
1. Cross-connector imports can violate layering and block independent
   release cadence.
1. Streaming failures can be under-reported if error mapping is not
   standardized at client and service boundaries.

## Mitigations

1. Keep one minimal shared AI contract for neutral primitives only:
   message, tool-call, tool-result, completion, usage, stream-chunk.
1. Keep provider-specific fields in connector-local adapters.
1. Enforce a no-cross-import rule between Salesforce and LLM connectors.
1. Require sync and async parity tests for interrupted streams,
   partial chunks, and timeout or cancel paths.

## Related ADRs

- [ADR-0021 Generic LLM Contract Boundary](../adr/0021-llm-contract-boundary.md)
- [SF-0011 Salesforce AI Connector Boundary](../../connectors/salesforce/architecture/adr/sf-0011-ai-connector-boundary.md)
