# Generic LLM Connector Guide

This guide documents the generic, provider-agnostic LLM connector in
`plynth.connectors.llm`.

The connector provides:

- neutral request and response contract models,
- sync and async service parity,
- streaming and non-streaming generation paths,
- optional tool-calling contract fields,
- opaque provider extension fields for provider-local behavior.

The connector intentionally avoids provider-specific endpoint schemas and
does not depend on Salesforce connector internals.

## Terminology and scope

- `plynth.connectors.llm` is a **connector**: it defines a neutral LLM domain
  contract and orchestration surface.
- Provider-specific mapping components are **adapters** under this connector.

Current scope includes the generic contract, generic services, and provider
adapters for OpenAI Responses and Anthropic Messages.

Additional providers can reuse the same adapter contracts.

## Public API

- `LLMService` / `AsyncLLMService`
- `LLMGenerateRequest`
- `LLMMessage`
- `LLMToolDefinition`
- `LLMCompletion`
- `LLMStreamChunk`
- `LLMExecutionOptions`

## Quickstart (sync)

```python
from plynth.connectors.llm import LLMGenerateRequest, LLMService
from plynth.http.client import APIClient
from plynth.http.transport import HttpxSyncTransport

transport = HttpxSyncTransport()
client = APIClient(base_url="https://provider.example.com", transport=transport)
llm = LLMService(client)

request = LLMGenerateRequest(
    messages=[
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "Summarize this text."},
    ],
    model="demo-model",
)

completion = llm.generate(request)
print(completion.choices[0].message.content)
```

## Quickstart (streaming)

```python
stream = llm.generate_stream(request)

with stream as response:
    for chunk in llm.iter_stream_chunks(response):
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="")
```

`iter_stream_chunks()` expects SSE-style `data:` lines or raw JSON lines.
Terminal `[DONE]` markers are ignored.

Use `iter_stream_chunks()` as the primary stream API. It handles SSE framing,
multi-line `data:` payloads, and parse error normalization. Keep
`parse_stream_line()` for utility and test scenarios where you have one fully
formed payload line.

## Stream event metadata

Provider adapters keep provider-specific event names in
`chunk.provider_extensions` and also emit a neutral `event_kind` value for
cross-provider observability.

- OpenAI examples: `text`, `tool`, `lifecycle`, `audio`, `error`.
- Anthropic examples: `text`, `tool`, `lifecycle`, `error`.

This keeps adapter behavior provider-specific while enabling generic metrics,
logging, and dashboards at the connector layer.

Runnable scripts are available in [examples/llm](../../../examples/llm/README.md).

Example usage:

```python
provider_meta = chunk.provider_extensions or {}
openai_meta = provider_meta.get("openai") or provider_meta.get("anthropic") or {}
event_kind = openai_meta.get("event_kind", "unknown")

metrics.increment("llm.stream.event", tags={"event_kind": event_kind})
```

## Async

```python
from plynth.connectors.llm import AsyncLLMService
from plynth.http.client import AsyncAPIClient
from plynth.http.transport import HttpxAsyncTransport

transport = HttpxAsyncTransport()
client = AsyncAPIClient(base_url="https://provider.example.com", transport=transport)
llm = AsyncLLMService(client)

completion = await llm.generate(request)
```

## Contract notes

- Provider-specific fields belong in `provider_extensions` only.
- Generic contract fields are intentionally minimal and connector-agnostic.
- Tool-calling is optional and represented as neutral typed structures.

For architecture rationale and boundaries, see:

- [ADR-0021 Generic LLM Contract Boundary](../../architecture/adr/0021-llm-contract-boundary.md)
- [SF-0011 Salesforce AI Connector Boundary](../salesforce/architecture/adr/sf-0011-ai-connector-boundary.md)
