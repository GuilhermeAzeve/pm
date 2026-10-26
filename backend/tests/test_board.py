import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import board
from app.db import connect, init_db
from app.main import create_app

SEED_BOARD = {
    "columns": [
        {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1", "card-2"]},
        {"id": "col-discovery", "title": "Discovery", "cardIds": ["card-3"]},
        {"id": "col-progress", "title": "In Progress", "cardIds": ["card-4", "card-5"]},
        {"id": "col-review", "title": "Review", "cardIds": ["card-6"]},
        {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8"]},
    ],
    "cards": {
        "card-1": {
            "id": "card-1",
            "title": "Align roadmap themes",
            "details": "Draft quarterly themes with impact statements and metrics.",
        },
        "card-2": {
            "id": "card-2",
            "title": "Gather customer signals",
            "details": "Review support tags, sales notes, and churn feedback.",
        },
        "card-3": {
            "id": "card-3",
            "title": "Prototype analytics view",
            "details": "Sketch initial dashboard layout and key drill-downs.",
        },
        "card-4": {
            "id": "card-4",
            "title": "Refine status language",
            "details": "Standardize column labels and tone across the board.",
        },
        "card-5": {
            "id": "card-5",
            "title": "Design card layout",
            "details": "Add hierarchy and spacing for scanning dense lists.",
        },
        "card-6": {
            "id": "card-6",
            "title": "QA micro-interactions",
            "details": "Verify hover, focus, and loading states.",
        },
        "card-7": {
            "id": "card-7",
            "title": "Ship marketing page",
            "details": "Final copy approved and asset pack delivered.",
        },
        "card-8": {
            "id": "card-8",
            "title": "Close onboarding sprint",
            "details": "Document release notes and share internally.",
        },
    },
}


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "nested" / "pm.db"


@pytest.fixture
def anon(tmp_path, db_path):
    with TestClient(create_app(tmp_path, db_path)) as client:
        yield client


@pytest.fixture
def client(anon):
    response = anon.post("/api/login", json={"username": "user", "password": "password"})
    assert response.status_code == 200
    return anon


def column(data, column_id):
    return next(c for c in data["columns"] if c["id"] == column_id)


def card_positions(db_path, column_id):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT position FROM cards WHERE column_id = ? ORDER BY position", (column_id,)
    ).fetchall()
    conn.close()
    return [row[0] for row in rows]


# Database setup and seeding


def test_startup_creates_directory_database_tables_and_user(anon, db_path):
    assert db_path.exists()
    conn = sqlite3.connect(db_path)
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    users = conn.execute("SELECT username FROM users").fetchall()
    boards = conn.execute("SELECT COUNT(*) FROM boards").fetchone()[0]
    conn.close()
    assert {"users", "boards", "board_columns", "cards"} <= tables
    assert users == [("user",)]
    assert boards == 0


def test_init_db_is_idempotent(db_path):
    init_db(db_path, ["user"])
    init_db(db_path, ["user"])
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    conn.close()


def test_connections_enforce_foreign_keys(db_path):
    init_db(db_path, ["user"])
    conn = connect(db_path)
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            conn.execute(
                "INSERT INTO cards (board_id, id, column_id, title, details, position)"
                " VALUES (999, 'card-x', 'col-x', 'X', '', 0)"
            )
    conn.close()


def test_first_board_request_seeds_initial_data(client):
    response = client.get("/api/board")
    assert response.status_code == 200
    assert response.json() == SEED_BOARD


def test_seed_is_idempotent_and_preserves_changes(client, db_path):
    client.patch("/api/columns/col-backlog", json={"title": "Ideas"})
    client.get("/api/board")
    data = client.get("/api/board").json()
    assert column(data, "col-backlog")["title"] == "Ideas"

    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM boards").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM board_columns").fetchone()[0] == 5
    assert conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 8
    conn.close()


def test_data_persists_across_app_instances(tmp_path, db_path, client):
    client.delete("/api/cards/card-1")
    with TestClient(create_app(tmp_path, db_path)) as second:
        second.post("/api/login", json={"username": "user", "password": "password"})
        data = second.get("/api/board").json()
    assert "card-1" not in data["cards"]


# Authentication


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/api/board", None),
        ("PATCH", "/api/columns/col-backlog", {"title": "X"}),
        ("POST", "/api/cards", {"columnId": "col-backlog", "title": "X", "details": ""}),
        ("PATCH", "/api/cards/card-1", {"title": "X", "details": ""}),
        ("POST", "/api/cards/card-1/move", {"columnId": "col-done", "position": 0}),
        ("DELETE", "/api/cards/card-1", None),
    ],
)
def test_board_routes_reject_anonymous(anon, db_path, method, path, body):
    response = anon.request(method, path, json=body)
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM boards").fetchone()[0] == 0
    conn.close()


def test_forged_session_is_rejected(anon):
    anon.cookies.set("pm_session", "user.forged")
    assert anon.get("/api/board").status_code == 401


# Columns


def test_rename_column_trims_title(client):
    response = client.patch("/api/columns/col-review", json={"title": "  QA  "})
    assert response.status_code == 200
    assert column(response.json(), "col-review")["title"] == "QA"
    assert column(client.get("/api/board").json(), "col-review")["title"] == "QA"


@pytest.mark.parametrize("body", [{"title": "   "}, {"title": ""}, {"title": 5}, {}])
def test_rename_column_rejects_invalid_body(client, body):
    assert client.patch("/api/columns/col-review", json=body).status_code == 422


def test_rename_unknown_column_is_not_found(client):
    assert client.patch("/api/columns/col-x", json={"title": "X"}).status_code == 404


# Cards


def test_create_card_appends_to_column(client, db_path):
    response = client.post(
        "/api/cards", json={"columnId": "col-review", "title": "  New  ", "details": "Notes"}
    )
    assert response.status_code == 201
    data = response.json()
    card_ids = column(data, "col-review")["cardIds"]
    assert card_ids[0] == "card-6"
    new_id = card_ids[1]
    assert new_id.startswith("card-")
    assert data["cards"][new_id] == {"id": new_id, "title": "New", "details": "Notes"}
    assert card_positions(db_path, "col-review") == [0, 1]


def test_create_card_allows_empty_details(client):
    response = client.post(
        "/api/cards", json={"columnId": "col-review", "title": "T", "details": ""}
    )
    new_id = column(response.json(), "col-review")["cardIds"][-1]
    assert response.json()["cards"][new_id]["details"] == ""


@pytest.mark.parametrize(
    "body",
    [
        {"columnId": "col-review", "title": " ", "details": ""},
        {"columnId": "col-review", "title": "T"},
        {"columnId": "col-review", "title": "T", "details": 3},
        {"columnId": "col-review", "title": "T", "details": None},
        {"title": "T", "details": ""},
    ],
)
def test_create_card_rejects_invalid_body(client, body):
    assert client.post("/api/cards", json=body).status_code == 422


def test_create_card_in_unknown_column_is_not_found(client):
    response = client.post("/api/cards", json={"columnId": "col-x", "title": "T", "details": ""})
    assert response.status_code == 404
    assert len(client.get("/api/board").json()["cards"]) == 8


def test_update_card(client):
    response = client.patch("/api/cards/card-3", json={"title": " Edited ", "details": ""})
    assert response.status_code == 200
    assert response.json()["cards"]["card-3"] == {"id": "card-3", "title": "Edited", "details": ""}
    assert column(response.json(), "col-discovery")["cardIds"] == ["card-3"]


@pytest.mark.parametrize("body", [{"title": "", "details": ""}, {"title": "T"}, {"details": ""}])
def test_update_card_rejects_invalid_body(client, body):
    assert client.patch("/api/cards/card-3", json=body).status_code == 422


def test_update_unknown_card_is_not_found(client):
    assert client.patch("/api/cards/card-x", json={"title": "T", "details": ""}).status_code == 404


def test_delete_card_compacts_positions(client, db_path):
    client.post("/api/cards", json={"columnId": "col-backlog", "title": "Third", "details": ""})
    response = client.delete("/api/cards/card-1")
    assert response.status_code == 200
    data = response.json()
    assert "card-1" not in data["cards"]
    assert column(data, "col-backlog")["cardIds"][0] == "card-2"
    assert len(column(data, "col-backlog")["cardIds"]) == 2
    assert card_positions(db_path, "col-backlog") == [0, 1]


def test_delete_unknown_card_is_not_found(client):
    assert client.delete("/api/cards/card-x").status_code == 404


# Moves


def move(client, card_id, column_id, position):
    return client.post(f"/api/cards/{card_id}/move", json={"columnId": column_id, "position": position})


def test_move_within_column(client, db_path):
    response = move(client, "card-2", "col-backlog", 0)
    assert response.status_code == 200
    assert column(response.json(), "col-backlog")["cardIds"] == ["card-2", "card-1"]
    assert card_positions(db_path, "col-backlog") == [0, 1]


def test_move_within_column_to_last_index(client):
    response = move(client, "card-1", "col-backlog", 1)
    assert column(response.json(), "col-backlog")["cardIds"] == ["card-2", "card-1"]


def test_move_to_same_position_is_unchanged(client):
    response = move(client, "card-1", "col-backlog", 0)
    assert response.status_code == 200
    assert response.json() == SEED_BOARD


def test_move_across_columns(client, db_path):
    response = move(client, "card-1", "col-done", 1)
    assert response.status_code == 200
    data = response.json()
    assert column(data, "col-backlog")["cardIds"] == ["card-2"]
    assert column(data, "col-done")["cardIds"] == ["card-7", "card-1", "card-8"]
    assert card_positions(db_path, "col-backlog") == [0]
    assert card_positions(db_path, "col-done") == [0, 1, 2]


def test_move_to_end_and_into_empty_column(client):
    move(client, "card-6", "col-done", 2)
    data = move(client, "card-7", "col-review", 0).json()
    assert column(data, "col-review")["cardIds"] == ["card-7"]
    assert column(data, "col-done")["cardIds"] == ["card-8", "card-6"]


@pytest.mark.parametrize(
    ("column_id", "position"), [("col-backlog", 2), ("col-done", 3), ("col-done", -1)]
)
def test_move_out_of_bounds_is_rejected(client, column_id, position):
    assert move(client, "card-1", column_id, position).status_code == 422
    assert client.get("/api/board").json() == SEED_BOARD


@pytest.mark.parametrize(
    "body",
    [{"columnId": "col-done"}, {"position": 0}, {"columnId": "col-done", "position": "1"},
     {"columnId": "col-done", "position": 1.5}],
)
def test_move_rejects_invalid_body(client, body):
    assert client.post("/api/cards/card-1/move", json=body).status_code == 422


def test_move_unknown_card_or_column_is_not_found(client):
    assert move(client, "card-x", "col-done", 0).status_code == 404
    assert move(client, "card-1", "col-x", 0).status_code == 404
    assert client.get("/api/board").json() == SEED_BOARD


# Per-user isolation (MVP login is hardcoded, so a second user is created directly)


@pytest.fixture
def two_boards(db_path):
    init_db(db_path, ["user", "other"])
    conn = connect(db_path)
    with conn:
        user_board = board.get_or_create_board_id(conn, "user")
        other_board = board.get_or_create_board_id(conn, "other")
    yield conn, user_board, other_board
    conn.close()


def test_each_user_gets_own_seeded_board(two_boards):
    conn, user_board, other_board = two_boards
    assert user_board != other_board
    assert board.get_board(conn, user_board) == SEED_BOARD
    assert board.get_board(conn, other_board) == SEED_BOARD


def test_mutations_only_affect_own_board(two_boards):
    conn, user_board, other_board = two_boards
    with conn:
        board.rename_column(conn, user_board, "col-backlog", "Mine")
        board.update_card(conn, user_board, "card-3", "Mine", "")
        board.move_card(conn, user_board, "card-1", "col-done", 0)
        board.delete_card(conn, user_board, "card-8")
        board.create_card(conn, user_board, "col-review", "Mine", "")
    assert board.get_board(conn, other_board) == SEED_BOARD
    assert board.get_board(conn, user_board) != SEED_BOARD


def test_cannot_reach_ids_on_another_board(two_boards):
    conn, user_board, other_board = two_boards
    with conn:
        other_card = board.create_card(conn, other_board, "col-review", "Other", "")
    for action in [
        lambda: board.update_card(conn, user_board, other_card, "X", ""),
        lambda: board.move_card(conn, user_board, other_card, "col-done", 0),
        lambda: board.delete_card(conn, user_board, other_card),
    ]:
        with pytest.raises(board.NotFoundError):
            with conn:
                action()
    assert other_card in board.get_board(conn, other_board)["cards"]
    assert other_card not in board.get_board(conn, user_board)["cards"]


def test_api_only_returns_session_users_board(client, db_path):
    init_db(db_path, ["user", "other"])
    conn = connect(db_path)
    with conn:
        other_board = board.get_or_create_board_id(conn, "other")
        other_card = board.create_card(conn, other_board, "col-review", "Other", "")
    conn.close()

    assert other_card not in client.get("/api/board").json()["cards"]
    assert client.delete(f"/api/cards/{other_card}").status_code == 404
    assert client.patch(f"/api/cards/{other_card}", json={"title": "X", "details": ""}).status_code == 404


def test_failed_service_call_rolls_back_transaction(two_boards):
    conn, user_board, _ = two_boards
    with pytest.raises(board.NotFoundError):
        with conn:
            board.rename_column(conn, user_board, "col-backlog", "Changed")
            board.move_card(conn, user_board, "card-x", "col-done", 0)
    assert column(board.get_board(conn, user_board), "col-backlog")["title"] == "Backlog"
