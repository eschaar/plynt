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

- Buffered calls through `SalesforceAPIClient` map Salesforce error payloads
  to typed connector exceptions. Generic `APIClient` instances provide HTTP
  status errors instead.
- Streaming calls map HTTP error statuses before returning the body.
  Streams are raw response wrappers, not Salesforce event parsers: event
  ordering and terminal markers pass through unchanged.
- Network failures during iteration raise `StreamInterruptedError`, retaining
  the original cause. Async cancellation propagates as `CancelledError`
  rather than being converted into a provider error.
- Use `with` or `async with` to close streams on completion, interruption,
  or cancellation.
- Keep retry behavior transport-level; do not retry after stream consumption has
  started.

## Feedback Validation

Request models require the relevant identifier and an integer rating.
Provider-specific rating ranges and identifier validity remain server-side
checks; this library does not invent a common rating scale.

Feedback acknowledgements preserve the server's `success` value.
Feedback submission has no client-side idempotency guarantee. Applications
must consider provider semantics before enabling retries for write requests.

## Compatibility Rules

- Preserve sync and async parity for every public method.
- Keep provider-specific model extensions additive and optional.
- Any breaking signature change requires ADR and release note entry.

## Test Coverage Strategy

### Implemented Contract Checks

[AI contract tests](../../../../tests/connectors/salesforce/test_ai_contracts.py)
exercise the services through real HTTP transports with HTTP-level mocks:

- Equivalent sync/async requests and typed results for all eight buffered
  Models and Agent methods.
- Ordered line delivery, including a synthetic terminal event, across
  fragmented HTTP chunks for both streaming methods.
- Partial output followed by a typed interruption, with no request replay.
- Async cancellation propagation and stream cleanup.
- Required feedback identifiers, invalid rating types, and equivalent
  server-validation error details in sync and async calls.
- Positive and negative feedback acknowledgements without rewriting the
  server's `success` value.

Existing service tests also cover optional payload fields and typed responses.
These checks validate the current library contracts, not provider availability.

### Remaining Provider Evidence

The HTTP fixtures and terminal events are synthetic. They do not prove actual
Salesforce event schemas, completion semantics, or provider rating ranges.
Recorded successful Models and Agent calls, streaming terminal events, and
provider-specific feedback errors remain separate validation work.

Keep live tests opt-in. Do not fabricate VCR cassettes or treat a disabled API
or an absent cassette as proof that the provider contract works.
