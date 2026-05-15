# Use the Salesforce Models API

`SalesforceModelsService` wraps the Salesforce Models API (Einstein).
It provides chat completions, text generation, embeddings, and response
feedback — all without managing a session.

## Prerequisites

A configured `SalesforceAPIFacade`:

```python
from plynth.connectors.salesforce.facade import SalesforceAPIFacade

sf = SalesforceAPIFacade(client)
models = sf.models()
```

______________________________________________________________________

## Chat completions

Send a list of messages and receive a single completion:

```python
from plynth.connectors.salesforce.models import ChatMessage

response = models.generate_chat(
    messages=[
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user",   content="Summarise this account in two sentences."),
    ],
)
print(response.generation.generated_text)
```

You can also pass raw dicts instead of `ChatMessage` objects:

```python
response = models.generate_chat(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user",   "content": "What is the capital of France?"},
    ],
    temperature=0.3,
    max_tokens=256,
)
```

`ChatCompletionResponse` fields:

| Field                       | Type  | Description                                     |
| --------------------------- | ----- | ----------------------------------------------- |
| `generation.generated_text` | `str` | The model's reply                               |
| `generation.finish_reason`  | `str` | Why the model stopped (`"stop"`, `"length"`, …) |
| `request_id`                | `str` | Use with `submit_feedback()`                    |

______________________________________________________________________

## Streaming chat completions

Set `stream=True` to receive the response incrementally. A
`StreamingResponse` is returned instead of a `ChatCompletionResponse`:

```python
stream = models.generate_chat(
    messages=[{"role": "user", "content": "Explain circuit breakers in one paragraph."}],
    stream=True,
)
for chunk in stream:
    print(chunk, end="", flush=True)
```

In async code, an `AsyncStreamingResponse` is returned:

```python
stream = await models.generate_chat(messages=messages, stream=True)
async for chunk in stream:
    print(chunk, end="", flush=True)
```

______________________________________________________________________

## Text generation

For single-turn text completion without a chat history:

```python
response = models.generate_text(
    prompt="Translate the following to Dutch: 'The weather is nice today.'",
    max_tokens=100,
)
print(response.generated_text)
```

`TextGenerationResponse` fields:

| Field            | Type  | Description                  |
| ---------------- | ----- | ---------------------------- |
| `generated_text` | `str` | The model's output           |
| `request_id`     | `str` | Use with `submit_feedback()` |

______________________________________________________________________

## Embeddings

Generate vector embeddings for semantic search or similarity comparison:

```python
response = models.generate_embeddings("Salesforce is a CRM platform.")
vector = response.embeddings[0].embedding
print(f"Dimension: {len(vector)}")
```

Batch multiple inputs in a single call:

```python
response = models.generate_embeddings([
    "Account closed — no further action",
    "Follow-up call scheduled for next week",
    "Contract renewed for two years",
])
for emb in response.embeddings:
    print(len(emb.embedding))
```

`EmbeddingResponse` fields:

| Field        | Type   | Description                                             |
| ------------ | ------ | ------------------------------------------------------- |
| `embeddings` | `list` | One entry per input; each has an `embedding` float list |
| `request_id` | `str`  | Use with `submit_feedback()`                            |

______________________________________________________________________

## Submit feedback

Rate a model response to improve future quality:

```python
models.submit_feedback(
    request_id=response.request_id,
    rating=4,                  # 1–5
    comment="Good summary but slightly too long",
)
```

______________________________________________________________________

## Specify a model

All three generation methods accept an optional `model` parameter. When
omitted, the Salesforce org default model is used:

```python
response = models.generate_chat(messages=messages, model="sfdc_ai__DefaultGPT4Omni")
```

______________________________________________________________________

## Async

```python
from plynth.connectors.salesforce.facade import AsyncSalesforceAPIFacade

sf = AsyncSalesforceAPIFacade(async_client)
models = sf.models()

response = await models.generate_chat(messages=messages, temperature=0.5)
embs = await models.generate_embeddings(["hello", "world"])
```

______________________________________________________________________

## See also

- [Use the Agentforce API](use-agent-api.md) — session-based agent
  interactions
- [Handle Salesforce errors](handle-errors.md)
- [Services reference](../reference/services.md)
