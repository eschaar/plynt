# Salesforce AI Models & Agents Design

Status: Implementation specification for Salesforce AI services.

## Scope

This design specifies the consumer-facing service contracts for:

- `SalesforceModelsService` / `AsyncSalesforceModelsService`
- `SalesforceAgentService` / `AsyncSalesforceAgentService`

Provider-specific payload fields remain connector-local and should not leak to
shared core abstractions.

## API Surface

### Models API

#### `generate_chat(...)`

- Input:
  - `messages: list[ChatMessage]`
  - `model: str | None = None`
  - `temperature: float | None = None`
  - `max_tokens: int | None = None`
  - `stream: bool = False`
  - `metadata: dict[str, str] | None = None`
- Output:
  - sync non-stream: `ChatCompletionResponse`
  - sync stream: `StreamingResponse` iterator wrapper
  - async stream: `AsyncStreamingResponse` iterator wrapper

#### `generate_text(...)`

- Input:
  - `prompt: str`
  - `model: str | None = None`
  - `temperature: float | None = None`
  - `max_tokens: int | None = None`
- Output:
  - `TextGenerationResponse`

#### `generate_embeddings(...)`

- Input:
  - `input_text: str | list[str]`
  - `model: str | None = None`
- Output:
  - `EmbeddingResponse`

#### `submit_feedback(...)` (models)

- Input:
  - `request_id: str`
  - `rating: int`
  - `comment: str | None = None`
- Output:
  - `FeedbackAck`

### Agent API

#### `start_session(...)`

- Input:
  - `agent_id: str`
  - `context: dict[str, str] | None = None`
- Output:
  - `AgentSession`

#### `send_message(...)`

- Input:
  - `session_id: str`
  - `text: str`
  - `metadata: dict[str, str] | None = None`
- Output:
  - `AgentMessageResponse`

#### `send_message_streaming(...)`

- Input:
  - `session_id: str`
  - `text: str`
  - `metadata: dict[str, str] | None = None`
- Output:
  - sync stream: `StreamingResponse` iterator wrapper
  - async stream: `AsyncStreamingResponse` iterator wrapper

#### `end_session(...)`

- Input:
  - `session_id: str`
- Output:
  - `AgentSessionEndAck`

#### `submit_feedback(...)` (agent)

- Input:
  - `session_id: str`
  - `message_id: str | None = None`
  - `rating: int`
  - `comment: str | None = None`
- Output:
  - `FeedbackAck`

## Error and Retry Contract

- Map HTTP status and Salesforce payload errors to typed Salesforce connector
  exceptions.
- Treat stream-interruption and cancellation as typed streaming errors.
- Keep retry behavior transport-level; do not retry after stream consumption has
  started.

## Compatibility Rules

- Preserve sync and async parity for every public method.
- Keep provider-specific model extensions additive and optional.
- Any breaking signature change requires ADR and release note entry.

## Test Coverage Strategy

### Critical Coverage Gaps

| Behavior                                                          | Current Weakness                                                       | Production Risk                                                       | Test Type   |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------- | --------------------------------------------------------------------- | ----------- |
| Streaming chat completion with chunk ordering and terminal marker | No streaming tests exist for chunk order and end-of-stream semantics   | Consumers may render incomplete or out-of-order model output          | integration |
| Stream interruption mid-response                                  | No connector-level tests for abrupt disconnect and typed error mapping | Silent partial output and hard-to-debug failures in user-facing flows | unit        |
| Sync and async parity across all methods                          | No parity suite exists for planned AI endpoints                        | Inconsistent behavior by runtime mode and regressions in one path     | contract    |
| Feedback endpoint validation and ack handling                     | No tests for invalid ratings, missing IDs, or idempotency expectations | Feedback data quality issues and unstable client retries              | unit        |

### False Confidence Risks

**Issue:** High coverage percentages can mask critical behavior gaps.

- **Generic HTTP transport tests only** — transport coverage does not prove
  Salesforce payload mapping correctness.

  - **Correction:** Add connector contract tests with representative Salesforce
    AI responses.

- **Planned AI services without streaming failure tests** — stream behavior is
  hard to test and easy to break.

  - **Correction:** Require explicit streaming failure tests and parity matrix
    checks as release gates.

### Priority Test Backlog

| Test Title                                                     | Owner  | Acceptance Criteria                                                           |
| -------------------------------------------------------------- | ------ | ----------------------------------------------------------------------------- |
| Models streaming chunks preserve order and finalize correctly  | tester | Stream tests assert deterministic chunk sequence and final completion marker. |
| Agent streaming interruption maps to typed stream error        | tester | Forced disconnect raises documented stream interruption exception.            |
| Models and Agent sync/async parity matrix                      | tester | For each public method, sync and async return equivalent semantic output.     |
| Feedback endpoint validation for invalid IDs and rating ranges | tester | Invalid payloads map to typed validation errors with stable messages.         |

### Test Implementation Notes

- Keep current fast mocked tests as baseline.
- Add VCR.py cassettes for deterministic Salesforce AI response fixtures.
- Keep optional live backend tests separate and opt-in.
