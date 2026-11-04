"""Live check of POST /api/ai/chat against a running app. Skipped unless enabled:

    PM_LIVE_BASE_URL=http://127.0.0.1:8000 uv run pytest tests/test_ai_chat_live.py

The app (normally the container from scripts/start.*) must have OPENROUTER_API_KEY. The
test asks the AI to create a uniquely titled card, confirms it through GET /api/board and
deletes only cards with that title afterwards.
"""

import os
import uuid

import httpx2
import pytest

BASE_URL = os.environ.get("PM_LIVE_BASE_URL")

pytestmark = pytest.mark.skipif(not BASE_URL, reason="set PM_LIVE_BASE_URL to run")


def test_ai_creates_card():
    title = f"Live AI test {uuid.uuid4().hex[:8]}"
    with httpx2.Client(base_url=BASE_URL, timeout=60) as client:
        login = client.post("/api/login", json={"username": "user", "password": "password"})
        assert login.status_code == 200
        before = client.get("/api/board").json()
        column = before["columns"][0]
        try:
            response = client.post(
                "/api/ai/chat",
                json={
                    "message": f'Create one card titled "{title}" with empty details in the'
                    f' "{column["title"]}" column. Make no other changes.'
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["reply"].strip()
            assert data["boardChanged"] is True
            created = [id for id, card in data["board"]["cards"].items() if card["title"] == title]
            assert len(created) == 1
            assert data["board"]["columns"][0]["cardIds"] == [*column["cardIds"], created[0]]
            stored = client.get("/api/board").json()
            assert stored == data["board"]
        finally:
            board = client.get("/api/board").json()
            for id, card in board["cards"].items():
                if card["title"] == title:
                    assert client.delete(f"/api/cards/{id}").status_code == 200
        assert client.get("/api/board").json() == before
