# Backend

FastAPI backend for the Project Management MVP, managed with `uv`. It serves authentication,
a health endpoint and the Next.js static export at `/`. No database or AI yet.

## Layout

```
pyproject.toml        Project metadata; runtime deps (fastapi, uvicorn); dev group (pytest, httpx2)
uv.lock               Locked dependency versions; keep in sync with pyproject.toml
app/
  main.py             create_app(static_dir): /api router plus static files mounted at /
tests/
  test_main.py        TestClient tests against a temporary static dir: health, index,
                      assets, 404 page, unknown /api route
```

## Routes

- `GET /api/health` returns `{"status": "ok"}`.
- `POST /api/login` accepts the hardcoded credentials `user` / `password`, sets a signed
  HTTP-only `pm_session` cookie and returns the username. Invalid credentials return 401.
- `GET /api/me` returns the signed-in username or 401.
- `POST /api/logout` clears the session cookie and returns 204.
- Unknown `/api/...` routes return FastAPI's JSON 404 response.
- Everything outside `/api` is served from the static directory by Starlette `StaticFiles`
  with `html=True`: `/` returns `index.html`, `/_next/...` assets, and unknown paths return
  `404.html` with status 404.

API routes live on the `api` router (`prefix="/api"`) and are registered before the static
mount, so registered `/api` routes take precedence over static files. Keep new API routes
under `/api`.

The session signature uses `SESSION_SECRET` when set, with a local-development default.
Sessions last one day and use `SameSite=Lax`.

## Static directory

`STATIC_DIR` comes from the `STATIC_DIR` environment variable, defaulting to
`frontend/out` in the repository. The mount uses `check_dir=False`, so the API runs even if
the frontend has not been built (static paths then return 404). The Docker image sets
`STATIC_DIR=/app/static`.

## Commands

Run from `backend/`:

- `uv sync` - create `.venv` with runtime and dev dependencies
- `uv run pytest` - run tests
- `uv run uvicorn app.main:app --reload` - local dev server on port 8000; run
  `npm run build` in `frontend/` first to serve the board
- `uv lock` after changing dependencies; `uv lock --check` to confirm the lock is current

## Docker

The root `Dockerfile` has two stages. The `node:24-slim` stage runs `npm ci` and
`npm run build` in `frontend/`. The `python:3.14-slim` stage copies `pyproject.toml`,
`uv.lock` and `app/` into `/app`, runs `uv sync --locked --no-dev`, copies the export to
`/app/static`, and starts `uvicorn app.main:app` on `0.0.0.0:8000` via `uv run --no-sync`.
No Node runtime, tests or dev dependencies are in the final image. `.env` is never copied;
the start scripts pass it at runtime with `--env-file` when it exists. See
`scripts/AGENTS.md`.

## Notes

- `requires-python = ">=3.14"`; the image uses `python:3.14-slim`.
- `httpx2` (dev group) is the HTTP client Starlette's `TestClient` uses.
