"""Live OpenRouter check. Skipped unless explicitly enabled:

    RUN_LIVE_AI=1 uv run pytest tests/test_ai_live.py

Requires OPENROUTER_API_KEY in the environment (in the container it comes from .env).
"""

import os

import pytest

from app import ai

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_AI") != "1", reason="set RUN_LIVE_AI=1 to call OpenRouter"
)


def test_two_plus_two():
    reply = ai.chat([{"role": "user", "content": "What is 2+2?"}])
    assert "4" in reply
