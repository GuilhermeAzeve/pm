"""Board services. Every function takes a connection inside a transaction and a board ID,
so HTTP routes and the Part 9 AI route can share them. Callers commit or roll back."""

import sqlite3
import uuid

SEED_COLUMNS = [
    ("col-backlog", "Backlog"),
    ("col-discovery", "Discovery"),
    ("col-progress", "In Progress"),
    ("col-review", "Review"),
    ("col-done", "Done"),
]

# (id, column_id, title, details), in column order.
SEED_CARDS = [
    ("card-1", "col-backlog", "Align roadmap themes",
     "Draft quarterly themes with impact statements and metrics."),
    ("card-2", "col-backlog", "Gather customer signals",
     "Review support tags, sales notes, and churn feedback."),
    ("card-3", "col-discovery", "Prototype analytics view",
     "Sketch initial dashboard layout and key drill-downs."),
    ("card-4", "col-progress", "Refine status language",
     "Standardize column labels and tone across the board."),
    ("card-5", "col-progress", "Design card layout",
     "Add hierarchy and spacing for scanning dense lists."),
    ("card-6", "col-review", "QA micro-interactions",
     "Verify hover, focus, and loading states."),
    ("card-7", "col-done", "Ship marketing page",
     "Final copy approved and asset pack delivered."),
    ("card-8", "col-done", "Close onboarding sprint",
     "Document release notes and share internally."),
]


class NotFoundError(Exception):
    pass


class InvalidMoveError(Exception):
    pass


def get_or_create_board_id(conn: sqlite3.Connection, username: str) -> int:
    user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if user is None:
        raise NotFoundError(f"Unknown user {username}")
    user_id = user[0]

    board = conn.execute("SELECT id FROM boards WHERE user_id = ?", (user_id,)).fetchone()
    if board is not None:
        return board[0]

    board_id = conn.execute("INSERT INTO boards (user_id) VALUES (?)", (user_id,)).lastrowid
    conn.executemany(
        "INSERT INTO board_columns (board_id, id, title, position) VALUES (?, ?, ?, ?)",
        [(board_id, id, title, i) for i, (id, title) in enumerate(SEED_COLUMNS)],
    )
    positions: dict[str, int] = {}
    rows = []
    for id, column_id, title, details in SEED_CARDS:
        position = positions.get(column_id, 0)
        positions[column_id] = position + 1
        rows.append((board_id, id, column_id, title, details, position))
    conn.executemany(
        "INSERT INTO cards (board_id, id, column_id, title, details, position)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    return board_id


def get_board(conn: sqlite3.Connection, board_id: int) -> dict:
    columns = conn.execute(
        "SELECT id, title FROM board_columns WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()
    cards = conn.execute(
        "SELECT id, column_id, title, details FROM cards"
        " WHERE board_id = ? ORDER BY column_id, position",
        (board_id,),
    ).fetchall()

    card_ids: dict[str, list[str]] = {column_id: [] for column_id, _ in columns}
    for id, column_id, _, _ in cards:
        card_ids[column_id].append(id)

    return {
        "columns": [
            {"id": id, "title": title, "cardIds": card_ids[id]} for id, title in columns
        ],
        "cards": {
            id: {"id": id, "title": title, "details": details}
            for id, _, title, details in cards
        },
    }


def rename_column(conn: sqlite3.Connection, board_id: int, column_id: str, title: str) -> None:
    updated = conn.execute(
        "UPDATE board_columns SET title = ? WHERE board_id = ? AND id = ?",
        (title, board_id, column_id),
    ).rowcount
    if not updated:
        raise NotFoundError(f"Unknown column {column_id}")


def create_card(
    conn: sqlite3.Connection, board_id: int, column_id: str, title: str, details: str
) -> str:
    card_ids = _column_card_ids(conn, board_id, column_id)
    card_id = f"card-{uuid.uuid4().hex[:12]}"
    conn.execute(
        "INSERT INTO cards (board_id, id, column_id, title, details, position)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (board_id, card_id, column_id, title, details, len(card_ids)),
    )
    return card_id


def update_card(
    conn: sqlite3.Connection, board_id: int, card_id: str, title: str, details: str
) -> None:
    updated = conn.execute(
        "UPDATE cards SET title = ?, details = ? WHERE board_id = ? AND id = ?",
        (title, details, board_id, card_id),
    ).rowcount
    if not updated:
        raise NotFoundError(f"Unknown card {card_id}")


def move_card(
    conn: sqlite3.Connection, board_id: int, card_id: str, column_id: str, position: int
) -> None:
    """Move a card so it ends at `position` in the target column's final list."""
    source_id = _card_column_id(conn, board_id, card_id)
    target = [id for id in _column_card_ids(conn, board_id, column_id) if id != card_id]
    if not 0 <= position <= len(target):
        raise InvalidMoveError(f"Position must be between 0 and {len(target)}")

    target.insert(position, card_id)
    layout = {column_id: target}
    if source_id != column_id:
        layout[source_id] = [
            id for id in _column_card_ids(conn, board_id, source_id) if id != card_id
        ]
    _write_layout(conn, board_id, layout)


def delete_card(conn: sqlite3.Connection, board_id: int, card_id: str) -> None:
    column_id = _card_column_id(conn, board_id, card_id)
    conn.execute("DELETE FROM cards WHERE board_id = ? AND id = ?", (board_id, card_id))
    _write_layout(conn, board_id, {column_id: _column_card_ids(conn, board_id, column_id)})


def _card_column_id(conn: sqlite3.Connection, board_id: int, card_id: str) -> str:
    row = conn.execute(
        "SELECT column_id FROM cards WHERE board_id = ? AND id = ?", (board_id, card_id)
    ).fetchone()
    if row is None:
        raise NotFoundError(f"Unknown card {card_id}")
    return row[0]


def _column_card_ids(conn: sqlite3.Connection, board_id: int, column_id: str) -> list[str]:
    exists = conn.execute(
        "SELECT 1 FROM board_columns WHERE board_id = ? AND id = ?", (board_id, column_id)
    ).fetchone()
    if exists is None:
        raise NotFoundError(f"Unknown column {column_id}")
    rows = conn.execute(
        "SELECT id FROM cards WHERE board_id = ? AND column_id = ? ORDER BY position",
        (board_id, column_id),
    ).fetchall()
    return [row[0] for row in rows]


def _write_layout(
    conn: sqlite3.Connection, board_id: int, layout: dict[str, list[str]]
) -> None:
    """Write contiguous positions for the given columns' ordered card IDs.

    Positions are first shifted above the current range so the final writes never collide
    with the UNIQUE (board_id, column_id, position) constraint.
    """
    offset = conn.execute(
        "SELECT COALESCE(MAX(position), 0) + 1 FROM cards WHERE board_id = ?", (board_id,)
    ).fetchone()[0]
    for column_id in layout:
        conn.execute(
            "UPDATE cards SET position = position + ? WHERE board_id = ? AND column_id = ?",
            (offset, board_id, column_id),
        )
    for column_id, card_ids in layout.items():
        conn.executemany(
            "UPDATE cards SET column_id = ?, position = ? WHERE board_id = ? AND id = ?",
            [(column_id, i, board_id, id) for i, id in enumerate(card_ids)],
        )
