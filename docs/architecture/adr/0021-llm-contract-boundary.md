# ADR-0021: Generic LLM Contract Boundary

## Status

Accepted

## Context

Plynth now includes Salesforce AI services and plans a generic LLM connector.
Without a shared contract boundary, each provider integration will likely
define different request and response shapes. That would increase adapter
complexity and make cross-provider switching harder for consumers.

The shared layer must stay minimal. It should capture only provider-agnostic
concepts and must not encode provider endpoint shapes, auth assumptions, or
vendor-specific features. This keeps connector independence intact and aligns
with ADR-0003 dependency policy and SF-0011 connector boundary rules.

## Decision

Define a minimal generic LLM contract that all provider connectors can map to.

### 1. Shared contract primitives

The generic contract includes only these concepts:

- message
- tool call
- tool result
- completion
- usage
- stream chunk
- request-level execution options

These primitives must be neutral. They describe intent and outcomes, not
provider payload structure.

### 2. Scope of the generic contract

The generic contract covers:

- non-streaming text generation
- streaming text generation
- optional tool-calling workflow

The generic contract does not cover provider-specific APIs such as embedding,
image, audio, moderation, or safety-policy schemas.

### 3. Extension boundary

Provider-specific behavior is allowed only through explicit extension fields
that are opaque to the generic layer. The generic layer may carry extension
data but must not interpret or validate provider-local semantics.

### 4. Execution model parity

The contract is execution-model agnostic. Sync and async connectors use the
same contract types and behavior semantics, with transport differences handled
below the service boundary.

### 5. Dependency and layering rule

Provider connectors may depend on the generic contract layer. The generic
contract layer must not depend on provider connectors. Cross-provider imports
between connector packages are not allowed.

## Alternatives Considered

### Option A: Keep fully independent provider contracts

**Description:** Each connector defines its own request and response models.

**Pros:**

- No up-front abstraction work.
- Maximum provider freedom.

**Cons:**

- High long-term integration and maintenance cost.
- No consistent surface for multi-provider use cases.
- Harder migration between providers.

**Why rejected:** This raises complexity for consumers and repeats the same
mapping work in every connector.

### Option B: Build a feature-complete universal AI abstraction

**Description:** Model all known provider features in one large shared schema.

**Pros:**

- Rich shared feature set.
- Potentially fewer connector-specific extensions.

**Cons:**

- High risk of abstraction leakage.
- Slow to evolve and hard to keep coherent.
- Pushes provider-specific semantics into shared core.

**Why rejected:** This is premature and conflicts with the minimal-core
principle.

### Option C: Minimal generic contract with explicit extension points

**Description:** Share only neutral primitives and keep provider details local.

**Pros:**

- Stable common surface for consumers.
- Low coupling between connectors.
- Clear path to add providers with predictable mapping.

**Cons:**

- Some connector-level duplication remains.
- Feature parity across providers stays an adapter concern.

**Why chosen:** It gives useful standardization without over-coupling.

## Rationale

This decision optimizes for connector independence and long-term usability.
Consumers gain a predictable interface for common LLM workflows. Connectors
retain freedom to expose provider strengths through local extensions. The
result is a stable generic foundation with controlled complexity growth.

## Consequences

### Positive

- Easier onboarding of additional providers.
- Lower consumer switching cost between providers.
- Clear boundary between generic and provider-local behavior.

### Negative / Tradeoffs

- Provider adapters still need explicit mapping code.
- Some advanced provider features will remain outside the generic contract.

### Risks

- Extension fields may grow unchecked and reintroduce coupling.
- Semantics may drift between connector implementations.

Mitigations:

- Add contract conformance tests shared across connectors.
- Add boundary tests that block cross-provider imports.
- Review extension usage in architecture reviews before expansion.

## Implementation Readiness Criteria

Use these criteria as implementation gates for connector work that depends on
this ADR:

1. A generic contract module exists with only neutral primitives for message,
   tool call, tool result, completion, usage, stream chunk, and request
   options.
1. Generic contract models contain no provider-specific fields or enum values.
1. Sync and async service paths use the same contract types and preserve
   equivalent behavior semantics.
1. Contract conformance tests exist and are reusable for any provider
   connector implementation.
1. Boundary tests enforce that provider connectors do not import each other.
1. Extension fields are explicitly marked as opaque and are not interpreted by
   the generic contract layer.
1. Documentation defines what is in scope for the generic contract and what
   remains provider-local.

## Related ADRs

- ADR-0003: Dependency Policy
- ADR-0009: Service Layer
- ADR-0017: Streaming Response Support
- SF-0011: Salesforce AI Connector Boundary
