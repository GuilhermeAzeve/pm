# Backend

FastAPI backend for the Project Management MVP, managed with `uv`. It serves authentication,
a health endpoint, the SQLite-backed board API, an OpenRouter connectivity test route, the AI
board chat route and the Next.js static export at `/`. The approved design is in `docs/DATABASE.md` and `docs/schema.json`.

## Layout

```
pyproject.toml        Project metadata; runtime deps (fastapi, httpx2, uvicorn); dev group (pytest)
uv.lock               Locked dependency versions; keep in sync with pyproject.toml
.gitignore            Ignores data/ (local development database)
app/
  main.py             create_app(static_dir, database_path, ai_transport): auth, board and
                      AI routes, static mount
  db.py               DATABASE_PATH, connect() with foreign keys on, init_db() schema + users
  board.py            Seed data and board service functions (read, rename, card CRUD, move)
  ai.py               OpenRouter client: chat(messages, transport, response_format) -> text
  assistant.py        AI chat: prompt, Structured Outputs schema, result validation, applying
                      operations through board.py
tests/
  test_main.py        Health, auth, static serving and /api 404 behavior
  test_board.py       Database setup, seeding, every board route, validation, ordering,
                      moves, deletion compaction, anonymous rejection, per-user isolation
  test_ai.py          /api/ai/test with a mocked OpenRouter transport (no key or network)
  test_ai_live.py     Live "What is 2+2?" check; skipped unless RUN_LIVE_AI=1
  test_ai_chat.py     /api/ai/chat with a mocked transport: request contract, validation,
                      each operation, invalid output, rollback, provider errors, isolation
  test_ai_chat_live.py Live create-card check against a running app; skipped unless
                      PM_LIVE_BASE_URL is set
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
- `POST /api/ai/test` with `{prompt}` (signed in; trimmed, non-empty) returns `{reply}`.
  401 anonymous (checked before any provider call), 422 invalid body, 503
  `{"detail": "AI is not configured"}` without `OPENROUTER_API_KEY`, 502
  `{"detail": "AI provider request failed"}` for provider HTTP, network or malformed
  responses. Provider bodies are never returned.
- `POST /api/ai/chat` with `{message, history}` (signed in). `message` is trimmed and
  non-empty; `history` (default `[]`) is a client-supplied list of
  `{role: "user" | "assistant", content}` with trimmed, non-empty content. History is not
  stored. Returns `{reply, boardChanged, board}`: `boardChanged` false and `board` null for a
  reply only, or true with the updated `BoardData`. 401 anonymous (before any database or
  provider access), 422 invalid body, 503 without the key, 502
  `{"detail": "AI provider request failed"}` for provider HTTP, network or malformed
  responses, and 502 `{"detail": "AI returned an invalid response"}` when the model result
  fails validation or any operation cannot be applied (unknown ID, out-of-range position).
  On any 502 no operation is kept.
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

## AI

- `ai.chat` POSTs `{model, messages}` to `https://openrouter.ai/api/v1/chat/completions`
  with model `openai/gpt-oss-120b`, `Authorization: Bearer <OPENROUTER_API_KEY>` and a
  30 second timeout, and returns the first choice's message content.
- The key is read from the environment on every call (the start scripts pass `.env` with
  `--env-file`). It is never logged or returned, and errors are raised `from None` so the
  original request is not attached.
- `create_app(..., ai_transport=...)` injects an `httpx2` transport; tests use
  `httpx2.MockTransport`. `None` uses the real network.
- Live check: `RUN_LIVE_AI=1 uv run pytest tests/test_ai_live.py` with the key set.
- With `response_format`, `ai.chat` also sends `provider: {require_parameters: true}` so
  OpenRouter only routes to providers that support Structured Outputs.

### Chat route (`assistant.py`)

- Messages sent: one system message (instructions, the allowed operations and the user's
  full `BoardData` as JSON), then the validated history, then the current message.
- `response_format` is `{type: "json_schema", json_schema: {name: "board_assistant_result",
  strict: true, schema: SCHEMA}}`. The schema has `additionalProperties: false` and every
  property required on every object:
  - `reply`: string shown to the user
  - `operations`: ordered array (empty for a reply only) of one of
    - `{type: "create", columnId, title, details}` (appended to the column)
    - `{type: "edit", cardId, title, details}`
    - `{type: "move", cardId, columnId, position}` (same meaning as the move route)
- The content is parsed and validated locally with pydantic in strict mode even though
  strict output is requested: extra fields are rejected, IDs and titles are trimmed and
  non-empty, `details` may be empty, `position` is a non-negative integer (not a bool,
  float or string). The whole result is validated before any change.
- Operations are applied in order with the `board.py` service functions, scoped to the
  signed-in user's board. The board is read and committed before the provider call so the
  database is not locked while waiting; the operations run in the request's next
  transaction, and any failure raises and rolls them all back.
- Delete and column rename are not AI operations.
- Live check: start the container, then
  `PM_LIVE_BASE_URL=http://127.0.0.1:8000 uv run pytest tests/test_ai_chat_live.py`. It
  asks the AI to create a uniquely titled card in the first column, checks the response and
  `GET /api/board`, deletes only that card and asserts the board matches its earlier state
  (so it fails if someone edits the board at the same time).

## Static directory

`STATIC_DIR` comes from the `STATIC_DIR` environment variable, defaulting to
`frontend/out` in the repository. The mount uses `check_dir=False`, so the API runs even if
the frontend has not been built (static paths then return 404). The Docker image sets
`STATIC_DIR=/app/static`.

## Commands

Run from `backend/`:

- `uv sync` - create `.venv` with runtime and dev dependencies
- `uv run pytest` - run tests (each test uses its own temporary database; the live AI
  tests are skipped)
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
- `httpx2` is a runtime dependency (OpenRouter client) and is also what Starlette's
  `TestClient` uses.
