# SF-0011 — Salesforce AI Connector Boundary

**Status:** Accepted
**Date:** 2026-05-14
**Scope:** `plynt.connectors.salesforce`, `plynt.connectors.llm`

______________________________________________________________________

## Context

Plynt has two parallel AI tracks:

- Salesforce-specific AI APIs (`Models` and `Agent` services)
- A generic provider-agnostic LLM connector

Both tracks need streaming support and typed request and response handling.
Without explicit boundaries, cross-connector dependencies can emerge and
create release coupling, abstraction leaks, and future extraction pain.

______________________________________________________________________

## Decision

### 1. Keep connectors independent

`plynt.connectors.salesforce` must not import from
`plynt.connectors.llm`, and `plynt.connectors.llm` must not import from
`plynt.connectors.salesforce`.

### 2. Share only neutral core primitives

Reusable behavior must flow through framework-agnostic core modules such as:

- transport abstractions (`plynt.base.transport`, `plynt.http`)
- streaming response primitives (`StreamingResponse`,
  `AsyncStreamingResponse`)
- middleware (`retry`, `rate_limit`, `auth`, `logging`, `cache`)
- typed base models and mapping helpers where provider-neutral

### 3. Keep provider-specific semantics local

Salesforce payload fields, endpoint quirks, and orchestration semantics stay
inside Salesforce services and models.

Generic provider abstractions stay in the LLM connector scope and must not
encode Salesforce-specific assumptions.

### 4. Keep parallel delivery independent

Salesforce Models API and Agent API can ship independently from the generic
LLM connector, as long as they follow the boundary rules above.

______________________________________________________________________

## Rationale

### Why not force a shared LLM connector first?

Forcing the generic connector first can delay Salesforce delivery and may
introduce premature abstractions before real provider differences are known.

### Why not share service-level code across connectors?

Service-level sharing tends to encode provider assumptions and makes
connector extraction harder. Shared code should stay one layer lower in core
transport and middleware primitives.

______________________________________________________________________

## Consequences

### Positive

- ✅ Connector release cadence stays independent.
- ✅ Clear layering supports later package extraction.
- ✅ Parallel work is possible without architecture drift.

### Negative

- ⚠️ Some short-term duplication is expected across connector service layers.
- ⚠️ Generic abstraction opportunities may be discovered later, not upfront.

______________________________________________________________________

## Follow-up

- Add guard checks in code review and CI for cross-connector imports.
- Draft a separate ADR for shared AI contract primitives if and when repeated
  cross-provider patterns are proven.
