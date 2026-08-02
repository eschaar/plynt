# LLM Examples

Markdown snippets for the generic LLM connector with provider adapters.

These examples are intentionally small but they demonstrate the full contract
path in this repository:

1. Build a neutral `LLMGenerateRequest`.
1. Select a provider adapter set.
1. Call one `LLMService` API for non-streaming and streaming.
1. Receive one neutral completion or stream-chunk shape.

## Snippets

| Script                  | Provider route                | Notes                                                                                             |
| ----------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------- |
| `openai_responses.md`   | OpenAI `POST /v1/responses`   | Uses `build_openai_responses_adapter_set()`                                                       |
| `anthropic_messages.md` | Anthropic `POST /v1/messages` | Uses `build_anthropic_messages_adapter_set()` and sends `x-api-key` + `anthropic-version` headers |

## Prerequisites

1. Install required extras:

```bash
pip install "plynth[httpx]"
```

1. Set provider credentials in `examples/llm/.env`.
1. Export variables in the active shell before running snippets.

## Quick start

```bash
cp examples/llm/example.env examples/llm/.env
# Fill values in examples/llm/.env, then export them in your shell.
set -a && source examples/llm/.env && set +a

# Open the markdown snippets and copy the code into your project.
# examples/llm/openai_responses.md
# examples/llm/anthropic_messages.md
```

## How these examples map to the connector

Both scripts use the same neutral service and request model:

- `LLMService`
- `LLMGenerateRequest`

Only adapter set and endpoint path differ:

- OpenAI: `build_openai_responses_adapter_set()` with `/responses`
- Anthropic: `build_anthropic_messages_adapter_set()` with `/messages`

This is the intended usage model for new provider integrations.

## Validation checklist

- Script prints `== Non-streaming ==` with non-empty assistant text.
- Script prints `== Streaming ==` with one or more chunk deltas.
- OpenAI and Anthropic snippets both run with the same neutral request model.

If streaming prints nothing, check API key, model, and provider endpoint.

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
