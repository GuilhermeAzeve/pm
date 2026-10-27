import json

import httpx2
import pytest
from fastapi.testclient import TestClient

from app import ai
from app.main import create_app

FAKE_KEY = "test-key-not-a-real-secret"


def completion(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


class FakeOpenRouter:
    """Records requests and replies with a configurable handler."""

    def __init__(self):
        self.requests: list[httpx2.Request] = []
        self.handler = lambda request: httpx2.Response(200, json=completion("4"))

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self.handler(request)


@pytest.fixture
def openrouter():
    return FakeOpenRouter()


@pytest.fixture
def anon(tmp_path, openrouter, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    app = create_app(tmp_path, tmp_path / "pm.db", ai_transport=httpx2.MockTransport(openrouter))
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client(anon):
    anon.post("/api/login", json={"username": "user", "password": "password"})
    return anon


def ask(client, prompt="What is 2+2?"):
    return client.post("/api/ai/test", json={"prompt": prompt})


def test_returns_reply_and_sends_expected_request(client, openrouter):
    response = ask(client, "  What is 2+2?  ")

    assert response.status_code == 200
    assert response.json() == {"reply": "4"}
    assert len(openrouter.requests) == 1
    request = openrouter.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
    assert request.headers["content-type"] == "application/json"
    assert json.loads(request.content) == {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": "What is 2+2?"}],
    }


def test_rejects_anonymous_before_calling_provider(anon, openrouter):
    response = ask(anon)
    assert response.status_code == 401
    assert openrouter.requests == []


@pytest.mark.parametrize("body", [{}, {"prompt": ""}, {"prompt": "   "}, {"prompt": 4}])
def test_rejects_invalid_body(client, openrouter, body):
    assert client.post("/api/ai/test", json=body).status_code == 422
    assert openrouter.requests == []


def test_missing_key_returns_503(client, openrouter, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    response = ask(client)
    assert response.status_code == 503
    assert response.json() == {"detail": "AI is not configured"}
    assert openrouter.requests == []


def test_upstream_status_error_returns_502_without_leaking(client, openrouter):
    openrouter.handler = lambda request: httpx2.Response(
        401, json={"error": {"message": "provider secret detail"}}
    )
    response = ask(client)
    assert response.status_code == 502
    assert response.json() == {"detail": "AI provider request failed"}
    assert "provider secret detail" not in response.text
    assert FAKE_KEY not in response.text


def test_network_error_returns_502(client, openrouter):
    def fail(request):
        raise httpx2.ConnectError("connection refused", request=request)

    openrouter.handler = fail
    response = ask(client)
    assert response.status_code == 502
    assert FAKE_KEY not in response.text


@pytest.mark.parametrize(
    "reply",
    [
        httpx2.Response(200, text="not json"),
        httpx2.Response(200, json={}),
        httpx2.Response(200, json={"choices": []}),
        httpx2.Response(200, json={"choices": [{"message": {}}]}),
        httpx2.Response(200, json=completion(None)),
        httpx2.Response(200, json=completion("   ")),
        httpx2.Response(200, json=["unexpected"]),
    ],
)
def test_malformed_or_empty_response_returns_502(client, openrouter, reply):
    openrouter.handler = lambda request: reply
    response = ask(client)
    assert response.status_code == 502
    assert response.json() == {"detail": "AI provider request failed"}


def test_chat_errors_do_not_include_the_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)

    def fail(request):
        raise httpx2.ConnectError(f"failed with {request.headers['authorization']}")

    with pytest.raises(ai.AIUpstreamError) as error:
        ai.chat([{"role": "user", "content": "hi"}], transport=httpx2.MockTransport(fail))
    assert FAKE_KEY not in str(error.value)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__


def test_chat_uses_bounded_timeout(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    seen = {}

    def handler(request):
        seen["timeout"] = request.extensions["timeout"]
        return httpx2.Response(200, json=completion("ok"))

    assert ai.chat([{"role": "user", "content": "hi"}], transport=httpx2.MockTransport(handler)) == "ok"
    assert seen["timeout"]["read"] == ai.TIMEOUT_SECONDS
