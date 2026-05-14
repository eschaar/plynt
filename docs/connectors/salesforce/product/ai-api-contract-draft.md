# Salesforce AI API Contract Draft

Status: Draft proposal for implementation planning.

## Scope

This draft defines the consumer-facing method contracts for:

- `SalesforceModelsService` / `AsyncSalesforceModelsService`
- `SalesforceAgentService` / `AsyncSalesforceAgentService`

Provider-specific payload fields remain connector-local and should not leak to
shared core abstractions.

## Models API Surface

### `generate_chat(...)`

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

### `generate_text(...)`

- Input:
  - `prompt: str`
  - `model: str | None = None`
  - `temperature: float | None = None`
  - `max_tokens: int | None = None`
- Output:
  - `TextGenerationResponse`

### `generate_embeddings(...)`

- Input:
  - `input_text: str | list[str]`
  - `model: str | None = None`
- Output:
  - `EmbeddingResponse`

### `submit_feedback(...)` (models)

- Input:
  - `request_id: str`
  - `rating: int`
  - `comment: str | None = None`
- Output:
  - `FeedbackAck`

## Agent API Surface

### `start_session(...)`

- Input:
  - `agent_id: str`
  - `context: dict[str, str] | None = None`
- Output:
  - `AgentSession`

### `send_message(...)`

- Input:
  - `session_id: str`
  - `text: str`
  - `metadata: dict[str, str] | None = None`
- Output:
  - `AgentMessageResponse`

### `send_message_streaming(...)`

- Input:
  - `session_id: str`
  - `text: str`
  - `metadata: dict[str, str] | None = None`
- Output:
  - sync stream: `StreamingResponse` iterator wrapper
  - async stream: `AsyncStreamingResponse` iterator wrapper

### `end_session(...)`

- Input:
  - `session_id: str`
- Output:
  - `AgentSessionEndAck`

### `submit_feedback(...)` (agent)

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
