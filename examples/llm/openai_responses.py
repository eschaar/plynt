"""OpenAI Responses example using the generic LLM connector.

Environment variables:
- OPENAI_API_KEY (required)
- OPENAI_BASE_URL (optional, default: https://api.openai.com)
- LLM_MODEL (optional, default: gpt-4.1-mini)
- LLM_PROMPT (optional)
"""

from __future__ import annotations

import os

from plynth.connectors.llm import LLMGenerateRequest, LLMService
from plynth.connectors.llm.adapters import build_openai_responses_adapter_set
from plynth.http.client import APIClient
from plynth.http.middleware.auth import BearerTokenAuthMiddleware
from plynth.http.transport import HttpxSyncTransport


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    api_key = _required_env("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").strip()
    model = os.getenv("LLM_MODEL", "gpt-4.1-mini").strip()
    prompt = os.getenv(
        "LLM_PROMPT",
        "Write a one-sentence haiku about clean architecture.",
    ).strip()

    transport = HttpxSyncTransport(middlewares=[BearerTokenAuthMiddleware(api_key)])
    client = APIClient(base_url=base_url, transport=transport)
    llm = LLMService(
        client,
        base_path="/v1",
        adapter_set=build_openai_responses_adapter_set(),
    )

    request = LLMGenerateRequest(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )

    completion = llm.generate(request, path="/responses")
    print("== Non-streaming ==")
    print(completion.choices[0].message.content or "")

    print("\n== Streaming ==")
    with llm.generate_stream(request, path="/responses") as response:
        for chunk in llm.iter_stream_chunks(response):
            delta = chunk.choices[0].delta.content
            if delta:
                print(delta, end="", flush=True)
    print()


if __name__ == "__main__":
    main()
