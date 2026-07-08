"""Anthropic Messages example using the generic LLM connector.

Environment variables:
- ANTHROPIC_API_KEY (required)
- ANTHROPIC_BASE_URL (optional, default: https://api.anthropic.com)
- ANTHROPIC_API_VERSION (optional, default: 2023-06-01)
- ANTHROPIC_MODEL (optional, default: claude-sonnet-4-20250514)
- LLM_PROMPT (optional)
"""

from __future__ import annotations

import os

from plynth.connectors.llm import LLMGenerateRequest, LLMService
from plynth.connectors.llm.adapters import build_anthropic_messages_adapter_set
from plynth.http.client import APIClient
from plynth.http.transport import HttpxSyncTransport


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    api_key = _required_env("ANTHROPIC_API_KEY")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").strip()
    api_version = os.getenv("ANTHROPIC_API_VERSION", "2023-06-01").strip()
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514").strip()
    prompt = os.getenv(
        "LLM_PROMPT",
        "Write a one-sentence haiku about clean architecture.",
    ).strip()

    transport = HttpxSyncTransport()
    client = APIClient(
        base_url=base_url,
        transport=transport,
        headers={
            "x-api-key": api_key,
            "anthropic-version": api_version,
        },
    )
    llm = LLMService(
        client,
        base_path="/v1",
        adapter_set=build_anthropic_messages_adapter_set(),
    )

    request = LLMGenerateRequest(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )

    completion = llm.generate(request, path="/messages")
    print("== Non-streaming ==")
    print(completion.choices[0].message.content or "")

    print("\n== Streaming ==")
    with llm.generate_stream(request, path="/messages") as response:
        for chunk in llm.iter_stream_chunks(response):
            delta = chunk.choices[0].delta.content
            if delta:
                print(delta, end="", flush=True)
    print()


if __name__ == "__main__":
    main()
