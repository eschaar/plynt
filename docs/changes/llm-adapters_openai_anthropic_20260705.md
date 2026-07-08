# LLM Adapters Change Document (OpenAI and Anthropic)

status: BUILD
type: feature
reference: ROADMAP-7
last_modified: 2026-07-05

## Goal and Context

Build provider adapters for OpenAI and Anthropic on top of the existing
provider-agnostic LLM connector, while preserving core connector boundaries
and sync/async parity.

Requested outcome:

1. Implement OpenAI and Anthropic adapters without direct dependency leaks into
   generic LLM contracts.
1. Make adapter behavior testable without live provider credentials.
1. Keep an implementation record that can be reused for follow-up work.

Explicit non-goals:

1. No broad redesign of core `plynth.base` or `plynth.http` layers.
1. No provider SDK lock-in inside generic service classes.
1. No mandatory live integration tests in default CI.

Constraints and dependencies:

1. Follow connector versus adapter boundary from architecture docs.
1. Keep compatibility with existing `LLMService` and `AsyncLLMService` usage.
1. Pass repository quality gate before publication.

## AS-IS

Repository evidence:

1. Generic LLM connector is present and tested in
   `src/plynth/connectors/llm/`.
1. Generic LLM docs mention provider adapters as planned, not implemented in
   [docs/connectors/llm/README.md](../connectors/llm/README.md).
1. Product roadmap marks provider adapters as planned in
   [docs/product/roadmap.md](../product/roadmap.md).
1. A temporary publication plan exists in repository memory.

Current behavior summary:

1. The connector supports neutral request and response models.
1. Streaming parsing is generic and SSE-oriented.
1. There is no dedicated OpenAI or Anthropic adapter module yet.

## TO-BE

Target design:

1. Add adapter modules under `src/plynth/connectors/llm/adapters/`.
1. Start with OpenAI Responses API mapping as primary route.
1. Add Anthropic mapping after OpenAI patterns are validated.
1. Keep provider-specific data in `provider_extensions` only.
1. Keep generic service APIs stable for existing users.

Implementation sequence:

1. OpenAI non-streaming adapter MVP.
1. OpenAI streaming and function-call mapping.
1. Anthropic non-streaming and streaming mapping.
1. Adapter registry and provider settings wiring.
1. Docs, examples, and release hardening.

Publication intent:

1. Internal preview immediately after each merge to `main`.
1. Public release after quality gate and short soak window.

## Impact (high level)

Architecture and boundaries:

1. Connector remains generic; adapters own provider translation.
1. No framework-specific dependency added to core layers.

API and model implications:

1. No breaking change to generic LLM public models.
1. Adapter-level mapping introduces provider-specific request and response
   translation rules.

Security and privacy implications:

1. No secrets in code or tests.
1. Credential-dependent tests stay optional and skipped by default.
1. Keep support for stateless provider requests where possible.

Operational implications:

1. Add focused adapter tests to existing pytest suite.
1. No required runtime migration for current generic connector users.
1. Update docs and release notes for provider support matrix.

## Acceptance Criteria

1. OpenAI adapter supports non-streaming and streaming generation paths.
1. Anthropic adapter supports non-streaming and streaming generation paths.
1. Sync and async parity is verified for adapter behavior.
1. Generic LLM contracts remain provider-agnostic.
1. `make check` passes.
1. Docs include runnable examples for both adapters.
1. Publication timing follows the agreed staged rollout plan.

## Test Scenarios

Happy path:

1. OpenAI non-streaming payload maps to neutral completion model.
1. OpenAI streaming events map to neutral stream chunks.
1. Anthropic non-streaming payload maps to neutral completion model.
1. Anthropic streaming events map to neutral stream chunks.

Failure path:

1. Invalid provider payload raises clear parse or mapping errors.
1. Missing required provider fields are surfaced with actionable messages.
1. Unsupported event type handling does not crash stream iteration.

Regression path:

1. Existing generic stream parsing tests continue to pass.
1. Existing Salesforce connector tests remain unaffected.
1. Existing generic LLM service behavior remains backward compatible.

## Implementation Log

2026-07-05 (Step 1 started):

1. Added OpenAI adapter package and non-streaming Responses mapping:
   `src/plynth/connectors/llm/adapters/__init__.py`
   and `src/plynth/connectors/llm/adapters/openai.py`.
1. Extended generic services with optional response normalization adapters in
   `src/plynth/connectors/llm/service.py`.
1. Exposed adapter types and helpers through
   `src/plynth/connectors/llm/__init__.py`.
1. Added focused adapter tests in
   `tests/connectors/llm/adapters/test_openai.py`.
1. Verified lint, type-check, and focused tests for this increment.

2026-07-05 (adapter architecture generalization):

1. Replaced ad-hoc payload and response callables with a typed adapter set
   architecture used directly by `LLMService` and `AsyncLLMService`.
1. Added base adapter contracts and defaults in
   `src/plynth/connectors/llm/adapters/base.py`.
1. Switched OpenAI mapping to class-based adapters and an explicit
   `build_openai_responses_adapter_set()` entry point.
1. Updated service and adapter tests to validate request, completion, and
   stream adapter wiring with no backward-compat fallback path.

2026-07-05 (OpenAI scope completion):

1. Added explicit OpenAI Responses stream-event adapter logic for text deltas,
   function-call argument deltas, completed events, and error terminal events.
1. Replaced deprecated Redis `setex` usage with `set(..., ex=...)` in cache
   backend code to remove runtime deprecation warnings during tests.
1. Expanded OpenAI adapter tests to cover request, completion, and stream
   mapping branches with sync service integration coverage.
1. Verified full quality gate and coverage report after the above changes.

## References

1. [docs/connectors/llm/README.md](../connectors/llm/README.md)
1. [docs/product/roadmap.md](../product/roadmap.md)
1. [OpenAI migrate to Responses](https://developers.openai.com/api/docs/guides/migrate-to-responses)
1. [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
1. [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
