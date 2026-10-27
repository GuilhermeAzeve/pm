"""Minimal OpenRouter chat client. The API key is read from the environment on each call
and is never logged, returned or included in raised errors."""

import os

import httpx2

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"
TIMEOUT_SECONDS = 30.0


class AINotConfiguredError(Exception):
    pass


class AIUpstreamError(Exception):
    pass


def chat(messages: list[dict[str, str]], transport: httpx2.BaseTransport | None = None) -> str:
    """Send chat messages to OpenRouter and return the first assistant message content.

    `transport` lets tests replace the network with `httpx2.MockTransport`.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise AINotConfiguredError("OPENROUTER_API_KEY is not set")

    try:
        with httpx2.Client(transport=transport, timeout=TIMEOUT_SECONDS) as client:
            response = client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": MODEL, "messages": messages},
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
    except (httpx2.HTTPError, ValueError, KeyError, IndexError, TypeError):
        # `from None` drops the original exception, which may carry request details.
        raise AIUpstreamError("OpenRouter request failed") from None

    if not isinstance(content, str) or not content.strip():
        raise AIUpstreamError("OpenRouter returned an empty response")
    return content
