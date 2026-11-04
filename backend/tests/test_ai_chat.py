import copy
import json

import httpx2
import pytest
from fastapi.testclient import TestClient

from app import assistant, board
from app.db import connect, init_db
from app.main import create_app
from tests.test_board import SEED_BOARD

FAKE_KEY = "test-key-not-a-real-secret"


def completion(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def result(reply="Done.", operations=()):
    return json.dumps({"reply": reply, "operations": list(operations)})


class FakeOpenRouter:
    """Records requests and replies with the configured model content."""

    def __init__(self):
        self.requests: list[httpx2.Request] = []
        self.content = result("Hello.")
        self.handler = None

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.handler:
            return self.handler(request)
        return httpx2.Response(200, json=completion(self.content))

    def body(self, index=0):
        return json.loads(self.requests[index].content)


@pytest.fixture
def openrouter():
    return FakeOpenRouter()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "pm.db"


@pytest.fixture
def anon(tmp_path, db_path, openrouter, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    app = create_app(tmp_path, db_path, ai_transport=httpx2.MockTransport(openrouter))
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client(anon):
    anon.post("/api/login", json={"username": "user", "password": "password"})
    return anon


def chat(client, message="Hi", history=()):
    return client.post("/api/ai/chat", json={"message": message, "history": list(history)})


def board_with(**changes):
    """SEED_BOARD with column cardIds and card fields replaced."""
    data = copy.deepcopy(SEED_BOARD)
    for column in data["columns"]:
        if column["id"] in changes:
            column["cardIds"] = changes[column["id"]]
    return data


# Request sent to the model


def test_sends_board_context_history_and_structured_output_request(client, openrouter):
    history = [
        {"role": "user", "content": "  What is on the board?  "},
        {"role": "assistant", "content": "Eight cards."},
    ]
    response = chat(client, "  Thanks  ", history)

    assert response.status_code == 200
    assert len(openrouter.requests) == 1
    request = openrouter.requests[0]
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
    body = openrouter.body()
    assert set(body) == {"model", "messages", "response_format", "provider"}
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["provider"] == {"require_parameters": True}
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "board_assistant_result",
            "strict": True,
            "schema": assistant.SCHEMA,
        },
    }

    system, *rest = body["messages"]
    assert system["role"] == "system"
    assert system["content"].startswith(assistant.INSTRUCTIONS)
    assert json.loads(system["content"][len(assistant.INSTRUCTIONS):]) == SEED_BOARD
    assert rest == [
        {"role": "user", "content": "What is on the board?"},
        {"role": "assistant", "content": "Eight cards."},
        {"role": "user", "content": "Thanks"},
    ]


def test_history_defaults_to_empty(client, openrouter):
    assert client.post("/api/ai/chat", json={"message": "Hi"}).status_code == 200
    assert openrouter.body()["messages"][1:] == [{"role": "user", "content": "Hi"}]


def test_system_message_uses_current_board(client, openrouter):
    client.patch("/api/cards/card-1", json={"title": "Renamed", "details": "New"})
    chat(client)
    context = openrouter.body()["messages"][0]["content"][len(assistant.INSTRUCTIONS):]
    assert json.loads(context)["cards"]["card-1"]["title"] == "Renamed"


def test_schema_is_strict_everywhere():
    def check(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert node["required"] == list(node["properties"])
                for prop in node["properties"].values():
                    assert prop.get("description") or "anyOf" in prop.get("items", {})
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(assistant.SCHEMA)
    variants = assistant.SCHEMA["properties"]["operations"]["items"]["anyOf"]
    assert [v["properties"]["type"]["enum"] for v in variants] == [["create"], ["edit"], ["move"]]


# Authentication and request validation


def test_rejects_anonymous_before_database_or_provider(anon, openrouter, db_path):
    response = chat(anon)
    assert response.status_code == 401
    assert openrouter.requests == []
    conn = connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM boards").fetchone()[0] == 0
    conn.close()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"message": ""},
        {"message": "   "},
        {"message": 4},
        {"message": "Hi", "history": "nope"},
        {"message": "Hi", "history": [{"role": "system", "content": "x"}]},
        {"message": "Hi", "history": [{"role": "user", "content": "  "}]},
        {"message": "Hi", "history": [{"role": "user"}]},
        {"message": "Hi", "history": [{"content": "x"}]},
    ],
)
def test_rejects_invalid_request(client, openrouter, body):
    assert client.post("/api/ai/chat", json=body).status_code == 422
    assert openrouter.requests == []


# Results


def test_reply_only_does_not_change_board(client, openrouter):
    openrouter.content = result("  Nothing to change.  ")
    response = chat(client)
    assert response.status_code == 200
    assert response.json() == {"reply": "Nothing to change.", "boardChanged": False, "board": None}
    assert client.get("/api/board").json() == SEED_BOARD


def test_create(client, openrouter):
    openrouter.content = result(
        "Added.", [{"type": "create", "columnId": " col-review ", "title": " New ", "details": ""}]
    )
    response = chat(client, "Add a card")

    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "Added."
    assert data["boardChanged"] is True
    new_id = data["board"]["columns"][3]["cardIds"][1]
    assert data["board"]["cards"][new_id] == {"id": new_id, "title": "New", "details": ""}
    assert data["board"] == client.get("/api/board").json()


def test_edit(client, openrouter):
    openrouter.content = result(
        "Edited.", [{"type": "edit", "cardId": "card-3", "title": "Better", "details": "More"}]
    )
    data = chat(client).json()
    expected = board_with()
    expected["cards"]["card-3"] = {"id": "card-3", "title": "Better", "details": "More"}
    assert data["board"] == expected == client.get("/api/board").json()


def test_move_within_column(client, openrouter):
    openrouter.content = result(
        "Moved.", [{"type": "move", "cardId": "card-1", "columnId": "col-backlog", "position": 1}]
    )
    data = chat(client).json()
    assert data["board"] == board_with(**{"col-backlog": ["card-2", "card-1"]})


def test_move_across_columns(client, openrouter):
    openrouter.content = result(
        "Moved.", [{"type": "move", "cardId": "card-4", "columnId": "col-done", "position": 0}]
    )
    data = chat(client).json()
    assert data["board"] == board_with(
        **{"col-progress": ["card-5"], "col-done": ["card-4", "card-7", "card-8"]}
    )
    assert client.get("/api/board").json() == data["board"]


def test_multiple_operations_apply_in_order(client, openrouter):
    openrouter.content = result(
        "Done.",
        [
            {"type": "move", "cardId": "card-6", "columnId": "col-done", "position": 2},
            {"type": "edit", "cardId": "card-6", "title": "QA done", "details": ""},
            {"type": "move", "cardId": "card-7", "columnId": "col-review", "position": 0},
            {"type": "create", "columnId": "col-review", "title": "Retest", "details": "x"},
        ],
    )
    data = chat(client).json()
    review = data["board"]["columns"][3]["cardIds"]
    assert review[0] == "card-7"
    assert data["board"]["cards"][review[1]]["title"] == "Retest"
    assert data["board"]["columns"][4]["cardIds"] == ["card-8", "card-6"]
    assert data["board"]["cards"]["card-6"]["title"] == "QA done"
    assert data["board"] == client.get("/api/board").json()


# Invalid model output


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "[]",
        json.dumps({"reply": "Hi"}),
        json.dumps({"operations": []}),
        json.dumps({"reply": "  ", "operations": []}),
        json.dumps({"reply": 5, "operations": []}),
        json.dumps({"reply": "Hi", "operations": [], "extra": 1}),
        json.dumps({"reply": "Hi", "operations": {}}),
        result(operations=[{"type": "delete", "cardId": "card-1"}]),
        result(operations=[{"type": "rename", "columnId": "col-done", "title": "X"}]),
        result(operations=[{"type": "create", "columnId": "col-done", "title": "X"}]),
        result(operations=[{"type": "create", "columnId": "col-done", "title": " ", "details": ""}]),
        result(operations=[{"type": "create", "columnId": "", "title": "X", "details": ""}]),
        result(operations=[{"type": "create", "columnId": "col-done", "title": "X", "details": 1}]),
        result(operations=[
            {"type": "edit", "cardId": "card-1", "title": "X", "details": "", "columnId": "col-done"}
        ]),
        result(operations=[{"type": "move", "cardId": "card-1", "columnId": "col-done", "position": -1}]),
        result(operations=[{"type": "move", "cardId": "card-1", "columnId": "col-done", "position": "1"}]),
        result(operations=[{"type": "move", "cardId": "card-1", "columnId": "col-done", "position": 1.0}]),
        result(operations=[{"type": "move", "cardId": "card-1", "columnId": "col-done", "position": True}]),
        result(operations=[{"type": "move", "cardId": "card-1", "columnId": "col-done"}]),
        # A valid first operation must not be applied when a later one is malformed.
        result(operations=[
            {"type": "create", "columnId": "col-done", "title": "X", "details": ""},
            {"type": "move", "cardId": "card-1"},
        ]),
    ],
)
def test_structurally_invalid_output_returns_502_without_changes(client, openrouter, content):
    openrouter.content = content
    response = chat(client)
    assert response.status_code == 502
    assert response.json() == {"detail": "AI returned an invalid response"}
    assert client.get("/api/board").json() == SEED_BOARD


@pytest.mark.parametrize(
    "operation",
    [
        {"type": "create", "columnId": "col-missing", "title": "X", "details": ""},
        {"type": "edit", "cardId": "card-missing", "title": "X", "details": ""},
        {"type": "move", "cardId": "card-missing", "columnId": "col-done", "position": 0},
        {"type": "move", "cardId": "card-1", "columnId": "col-missing", "position": 0},
        {"type": "move", "cardId": "card-1", "columnId": "col-done", "position": 3},
        {"type": "move", "cardId": "card-1", "columnId": "col-backlog", "position": 2},
    ],
)
def test_unknown_ids_or_out_of_range_position_return_502(client, openrouter, operation):
    openrouter.content = result(operations=[operation])
    response = chat(client)
    assert response.status_code == 502
    assert response.json() == {"detail": "AI returned an invalid response"}
    assert client.get("/api/board").json() == SEED_BOARD


def test_later_failing_operation_rolls_back_earlier_ones(client, openrouter):
    openrouter.content = result(
        "Done.",
        [
            {"type": "create", "columnId": "col-backlog", "title": "Temp", "details": ""},
            {"type": "edit", "cardId": "card-1", "title": "Changed", "details": ""},
            {"type": "move", "cardId": "card-4", "columnId": "col-done", "position": 0},
            {"type": "move", "cardId": "card-5", "columnId": "col-done", "position": 99},
        ],
    )
    response = chat(client)
    assert response.status_code == 502
    assert client.get("/api/board").json() == SEED_BOARD


def test_rollback_keeps_lazily_seeded_board(client, openrouter, db_path):
    # The first request seeds the board; a failing operation must not undo the seed.
    openrouter.content = result(operations=[{"type": "edit", "cardId": "x", "title": "X", "details": ""}])
    assert chat(client).status_code == 502
    conn = connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 8
    conn.close()


# Provider failures


def test_missing_key_returns_503(client, openrouter, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    response = chat(client)
    assert response.status_code == 503
    assert response.json() == {"detail": "AI is not configured"}
    assert openrouter.requests == []


def test_provider_status_error_returns_502_without_leaking(client, openrouter):
    openrouter.handler = lambda request: httpx2.Response(
        400, json={"error": {"message": "provider secret detail"}}
    )
    response = chat(client)
    assert response.status_code == 502
    assert response.json() == {"detail": "AI provider request failed"}
    assert "provider secret detail" not in response.text
    assert FAKE_KEY not in response.text


def test_network_error_returns_502(client, openrouter):
    def fail(request):
        raise httpx2.ConnectError("connection refused", request=request)

    openrouter.handler = fail
    response = chat(client)
    assert response.status_code == 502
    assert response.json() == {"detail": "AI provider request failed"}


@pytest.mark.parametrize("body", [{}, {"choices": []}, completion(None), completion("  ")])
def test_malformed_provider_response_returns_502(client, openrouter, body):
    openrouter.handler = lambda request: httpx2.Response(200, json=body)
    response = chat(client)
    assert response.status_code == 502
    assert response.json() == {"detail": "AI provider request failed"}
    assert client.get("/api/board").json() == SEED_BOARD


def test_invalid_output_error_does_not_echo_content(client, openrouter):
    openrouter.content = "secret model text"
    response = chat(client)
    assert "secret model text" not in response.text


# Per-user isolation (MVP login is hardcoded, so a second user is created directly)


def read_board(db_path, board_id):
    # A short-lived connection, so no read transaction is held while the app writes.
    conn = connect(db_path)
    try:
        return board.get_board(conn, board_id)
    finally:
        conn.close()


@pytest.fixture
def other_board(db_path):
    init_db(db_path, ["user", "other"])
    conn = connect(db_path)
    with conn:
        board_id = board.get_or_create_board_id(conn, "other")
        other_card = board.create_card(conn, board_id, "col-review", "Other", "")
    conn.close()
    return board_id, other_card


def test_operations_only_touch_signed_in_board(client, openrouter, db_path, other_board):
    other_id, _ = other_board
    before = read_board(db_path, other_id)
    openrouter.content = result(
        "Done.",
        [
            {"type": "edit", "cardId": "card-1", "title": "Mine", "details": ""},
            {"type": "move", "cardId": "card-2", "columnId": "col-done", "position": 0},
        ],
    )
    assert chat(client).status_code == 200
    assert client.get("/api/board").json()["cards"]["card-1"]["title"] == "Mine"
    assert read_board(db_path, other_id) == before


@pytest.mark.parametrize("op_type", ["edit", "move"])
def test_cannot_reach_another_users_card(client, openrouter, db_path, other_board, op_type):
    other_id, other_card = other_board
    before = read_board(db_path, other_id)
    operation = (
        {"type": "edit", "cardId": other_card, "title": "Hijack", "details": ""}
        if op_type == "edit"
        else {"type": "move", "cardId": other_card, "columnId": "col-done", "position": 0}
    )
    openrouter.content = result(operations=[operation])
    assert chat(client).status_code == 502
    assert read_board(db_path, other_id) == before
    assert client.get("/api/board").json() == SEED_BOARD
    context = openrouter.body()["messages"][0]["content"]
    assert other_card not in context
