import os
import sqlite3
from pathlib import Path

# The start scripts set DATABASE_PATH=/data/pm.db on a named Docker volume.
DATABASE_PATH = Path(
    os.environ.get("DATABASE_PATH", Path(__file__).resolve().parents[1] / "data" / "pm.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS board_columns (
    board_id INTEGER NOT NULL REFERENCES boards (id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    title TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (board_id, id),
    UNIQUE (board_id, position)
);

CREATE TABLE IF NOT EXISTS cards (
    board_id INTEGER NOT NULL,
    id TEXT NOT NULL,
    column_id TEXT NOT NULL,
    title TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (board_id, id),
    UNIQUE (board_id, column_id, position),
    FOREIGN KEY (board_id, column_id)
        REFERENCES board_columns (board_id, id) ON DELETE CASCADE
);
"""


def connect(path: Path) -> sqlite3.Connection:
    # PRAGMA foreign_keys has no effect inside a transaction, so set it in autocommit
    # mode before switching to explicit transaction control.
    conn = sqlite3.connect(path, autocommit=True)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.autocommit = False
    return conn


def init_db(path: Path, usernames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        with conn:
            conn.executescript(SCHEMA)
            conn.executemany(
                "INSERT OR IGNORE INTO users (username) VALUES (?)",
                [(username,) for username in usernames],
            )
    finally:
        conn.close()
