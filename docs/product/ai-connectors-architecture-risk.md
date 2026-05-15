# AI Connectors Architecture Risk

## High-Severity Risks

- impacted boundary (contract)

- why it is risky in one sentence:
  Diverging request and response schemas between Salesforce AI services and the
  generic LLM connector will create incompatible abstractions and expensive
  rework.

- mitigation with smallest viable change:
  Define one minimal shared AI model contract in core-facing types only
  (`message`, `tool-call`, `stream-chunk`, `usage`) and keep provider-specific
  fields isolated in connector-local adapters.

- owner role:
  architect

- impacted boundary (service)

- why it is risky in one sentence:
  Cross-connector imports (Salesforce \<-> LLM) can silently violate layering
  and block independent releases.

- mitigation with smallest viable change:
  Add a strict no-cross-import rule in architecture guidance and tests that
  assert `src/plynth/connectors/salesforce` does not import
  `src/plynth/connectors/llm` and vice versa.

- owner role:
  engineer

- impacted boundary (observability)

- why it is risky in one sentence:
  Streaming failures during iteration can be under-reported because middleware
  is unwound before stream consumption.

- mitigation with smallest viable change:
  Standardize stream error mapping in client/service boundaries and require
  tests for interrupted streams, partial chunks, and timeout/cancel behavior.

- owner role:
  engineer

## Medium Risks

- Different auth assumptions (API key vs OAuth/session) can leak into shared
  interfaces and reduce generic usability.
- Test parity drift between sync and async APIs can grow unnoticed without a
  parity checklist and mirrored test cases.
- Endpoint naming drift across connectors can increase cognitive load for
  consumers.

## Tradeoff Notes

- Optimize for connector independence over early abstraction sharing.
- Optimize for a thin shared contract over feature-complete abstraction.
- Accept some duplication early to avoid premature coupling.

## Missing Decisions

- ADR: minimal shared AI contract boundary (what is generic vs provider-local).
- ADR: streaming error and cancellation semantics at client/service boundaries.
- ADR: packaging placement for generic AI connector (`plynth.connectors.llm`
  vs dedicated package).

## Recommended Sequence

1. Accept ADR for shared AI contract boundary and non-dependency rule.
1. Define Salesforce Models and Agent API contracts with provider-local models.
1. Add connector boundary tests and sync/async parity test matrix.
1. Implement Salesforce Models API and Agent API services.
1. Start generic LLM connector using validated shared primitives from step 1.
1. Run API and test-gap reviews before broad rollout.

## Security Considerations

- Enforce strict token redaction in logs for both OAuth and API key flows.
- Ensure streaming payloads do not log prompt or response bodies by default.
- Validate tool/function-call payloads before execution to avoid injection-like
  behavior in downstream consumers.
- Keep dependency additions for AI providers optional and isolated by extras.

## Go/No-Go

- conditional-go
- Proceed only after ADR decisions for shared AI boundaries and streaming error
  semantics are accepted.
