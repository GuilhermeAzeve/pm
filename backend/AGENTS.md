# Backend

FastAPI backend for the Project Management MVP, managed with `uv`. It serves authentication,
a health endpoint, the SQLite-backed board API and the Next.js static export at `/`. No AI
yet. The approved design is in `docs/DATABASE.md` and `docs/schema.json`.

## Layout

```
pyproject.toml        Project metadata; runtime deps (fastapi, uvicorn); dev group (pytest, httpx2)
uv.lock               Locked dependency versions; keep in sync with pyproject.toml
.gitignore            Ignores data/ (local development database)
app/
  main.py             create_app(static_dir, database_path): auth, board routes, static mount
  db.py               DATABASE_PATH, connect() with foreign keys on, init_db() schema + users
  board.py            Seed data and board service functions (read, rename, card CRUD, move)
tests/
  test_main.py        Health, auth, static serving and /api 404 behavior
  test_board.py       Database setup, seeding, every board route, validation, ordering,
                      moves, deletion compaction, anonymous rejection, per-user isolation
```

## Routes

- `GET /api/health` returns `{"status": "ok"}`.
- `POST /api/login` accepts the hardcoded credentials `user` / `password`, sets a signed
  HTTP-only `pm_session` cookie and returns the username. Invalid credentials return 401.
- `GET /api/me` returns the signed-in username or 401.
- `POST /api/logout` clears the session cookie and returns 204.
- Board routes (all require the session; 401 anonymous, 404 for IDs not on the user's
  board, 422 for invalid bodies or out-of-range move positions). Every success returns the
  full `BoardData` (`{columns: [{id, title, cardIds}], cards: {id: {id, title, details}}}`):
  - `GET /api/board`
  - `PATCH /api/columns/{column_id}` with `{title}`
  - `POST /api/cards` with `{columnId, title, details}` returns 201
  - `PATCH /api/cards/{card_id}` with `{title, details}`
  - `POST /api/cards/{card_id}/move` with `{columnId, position}`; `position` is the
    zero-based index in the target column after removing the card from its old place
  - `DELETE /api/cards/{card_id}`
  Titles are trimmed and must be non-empty; details must be strings and may be empty.
- Unknown `/api/...` routes return FastAPI's JSON 404 response.
- Everything outside `/api` is served from the static directory by Starlette `StaticFiles`
  with `html=True`: `/` returns `index.html`, `/_next/...` assets, and unknown paths return
  `404.html` with status 404.

API routes live on the `api` router (`prefix="/api"`) and are registered before the
catch-all `/api` 404 route and the static mount. Keep new API routes under `/api`, defined
before the catch-all.

The session signature uses `SESSION_SECRET` when set, with a local-development default.
Sessions last one day and use `SameSite=Lax`.

## Database

- SQLite via the standard library `sqlite3`. `DATABASE_PATH` comes from the environment,
  defaulting to `backend/data/pm.db`. The start scripts set `/data/pm.db` on the `pm-data`
  Docker volume.
- On startup (FastAPI lifespan) `init_db` creates the parent directory, the tables
  (`CREATE TABLE IF NOT EXISTS`) and the hardcoded `user` row. It is idempotent.
- `connect()` enables `PRAGMA foreign_keys` before switching to explicit transactions.
  Each request gets one connection and one transaction (`get_db`): committed on success,
  rolled back on any error.
- The board is seeded lazily: the first board request for a user with no board creates it
  with the five columns and eight cards from `frontend/src/lib/kanban.ts`. Later requests
  never reseed.
- Service functions in `board.py` take `(conn, board_id, ...)` and leave commit/rollback to
  the caller, so Part 9 can apply several operations in one transaction. They raise
  `NotFoundError` (mapped to 404) and `InvalidMoveError` (mapped to 422).
- Card positions stay contiguous from 0. Moves and deletes rewrite affected columns via
  `_write_layout`, which first shifts positions above the current range to avoid unique
  constraint collisions.
- New card IDs are `card-` plus 12 hex characters.

## Static directory

`STATIC_DIR` comes from the `STATIC_DIR` environment variable, defaulting to
`frontend/out` in the repository. The mount uses `check_dir=False`, so the API runs even if
the frontend has not been built (static paths then return 404). The Docker image sets
`STATIC_DIR=/app/static`.

## Commands

Run from `backend/`:

- `uv sync` - create `.venv` with runtime and dev dependencies
- `uv run pytest` - run tests (each test uses its own temporary database)
- `uv run uvicorn app.main:app --reload` - local dev server on port 8000, using
  `backend/data/pm.db`; run `npm run build` in `frontend/` first to serve the board
- `uv lock` after changing dependencies; `uv lock --check` to confirm the lock is current

## Docker

The root `Dockerfile` has two stages. The `node:24-slim` stage runs `npm ci` and
`npm run build` in `frontend/`. The `python:3.14-slim` stage copies `pyproject.toml`,
`uv.lock` and `app/` into `/app`, runs `uv sync --locked --no-dev`, copies the export to
`/app/static`, and starts `uvicorn app.main:app` on `0.0.0.0:8000` via `uv run --no-sync`.
No Node runtime, tests, dev dependencies or database file are in the final image. `.env`
is never copied; the start scripts pass it at runtime with `--env-file` when it exists, and
mount the database volume. See `scripts/AGENTS.md`.

## Notes

- `requires-python = ">=3.14"`; the image uses `python:3.14-slim`.
- `httpx2` (dev group) is the HTTP client Starlette's `TestClient` uses.
