# LLM Examples

Runnable scripts for the generic LLM connector with provider adapters.

These examples are intentionally small but they demonstrate the full contract
path in this repository:

1. Build a neutral `LLMGenerateRequest`.
1. Select a provider adapter set.
1. Call one `LLMService` API for non-streaming and streaming.
1. Receive one neutral completion or stream-chunk shape.

## Scripts

| Script                  | Provider route                | Notes                                                                                             |
| ----------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------- |
| `openai_responses.py`   | OpenAI `POST /v1/responses`   | Uses `build_openai_responses_adapter_set()`                                                       |
| `anthropic_messages.py` | Anthropic `POST /v1/messages` | Uses `build_anthropic_messages_adapter_set()` and sends `x-api-key` + `anthropic-version` headers |

## Quick start

```bash
cp examples/llm/example.env examples/llm/.env
# Fill values in examples/llm/.env, then export them in your shell.
set -a && source examples/llm/.env && set +a

python examples/llm/openai_responses.py
python examples/llm/anthropic_messages.py
```

## How these examples map to the connector

Both scripts use the same neutral service and request model:

- `LLMService`
- `LLMGenerateRequest`

Only adapter set and endpoint path differ:

- OpenAI: `build_openai_responses_adapter_set()` with `/responses`
- Anthropic: `build_anthropic_messages_adapter_set()` with `/messages`

This is the intended usage model for new provider integrations.

## What output to expect

Each script prints two sections:

1. `== Non-streaming ==`
   This prints the final assembled assistant text from one completion call.
1. `== Streaming ==`
   This prints incremental deltas from `iter_stream_chunks()` as tokens arrive.

If streaming prints nothing, check API key, model name, and provider endpoint.

Each script runs both a non-streaming and streaming request using the same
neutral `LLMGenerateRequest` model and `LLMService` API.

## Required environment variables

- `OPENAI_API_KEY` for OpenAI example
- `ANTHROPIC_API_KEY` for Anthropic example
- `ANTHROPIC_API_VERSION` for Anthropic version header (default provided)

Optional variables are listed in `example.env`.

## Troubleshooting

### OpenAI returns 401 or 403

- Verify `OPENAI_API_KEY` is exported in the active shell.
- Confirm the key has access to the selected model.

### Anthropic returns version header errors

- Set `ANTHROPIC_API_VERSION` to a valid value.
- Keep `anthropic-version` and `x-api-key` headers present.

### Both scripts return empty text

- Validate `LLM_PROMPT` is non-empty.
- Try a known working model and a short prompt first.
