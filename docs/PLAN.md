# Project Plan

Execution plan for the Project Management MVP described in the root `AGENTS.md`. Work the
parts in order. Check a box only after its work is done and its verification has passed.
Stop at each approval gate until the user explicitly approves.

## Fixed decisions

These come from the root `AGENTS.md` and apply to every part:

- Next.js frontend, statically built and served by a Python FastAPI backend at `/`.
- One Docker container; Python dependencies managed with `uv` inside it.
- SQLite database, created automatically if it does not exist.
- OpenRouter for AI calls, model `openai/gpt-oss-120b`, key read from `OPENROUTER_API_KEY`
  in the root `.env` (never committed, logged or printed).
- Start and stop scripts for Mac, Windows and Linux in `scripts/`.
- MVP limits: a single hardcoded login (`user` / `password`), one board per user, local
  only. The database schema still supports multiple users.
- Color scheme and coding standards from the root `AGENTS.md`. Keep it simple, no extra
  features, no emojis.

## Current state (before Part 2)

- `frontend/`: client-only Next.js Kanban demo. Five fixed renameable columns, add and
  delete cards, drag and drop, in-memory state only. No card editing, no backend calls,
  no persistence, no sign in, no AI. See `frontend/AGENTS.md`.
- `backend/` and `scripts/`: placeholder `AGENTS.md` files only.
- No Dockerfile, no database, no AI integration.

Everything below Part 1 is planned behavior, not current behavior. Details marked
"provisional" are proposals to confirm or adjust at the stated gate, not locked decisions.

## Part dependencies

- Part 2 provides the container, backend and scripts that every later part runs in.
- Part 3 depends on Part 2 and makes the existing frontend the app at `/`.
- Part 4 depends on Part 3 and adds the sign-in gate around the board.
- Part 5 is design only and gates Parts 6 and later.
- Part 6 depends on Part 5 approval; Part 7 depends on Parts 4 and 6.
- Part 8 depends on Part 2; Part 9 depends on Parts 6 and 8; Part 10 depends on Parts 7
  and 9.

---

## Part 1: Plan

Turn the high-level steps into this checklist and document the existing frontend.

### Steps

- [x] Inspect the repository, root guidance and existing frontend.
- [x] Rewrite `docs/PLAN.md` with substeps, tests and success criteria for Parts 1-10.
- [x] Create `frontend/AGENTS.md` describing the existing frontend code.
- [x] Add the agent collaboration model to the root `AGENTS.md`.
- [x] User reviews and approves this plan.

### Tests/Verification

- All ten parts are present, each with Steps, Tests/Verification and Success Criteria.
- `frontend/AGENTS.md` matches the files in `frontend/` (stack, components, commands,
  tests, limitations).
- `git diff --check` passes; only documentation files changed.

### Success Criteria

- A future agent can execute Parts 2-10 from this document without further planning.
- The user has explicitly approved the plan.

**Approval gate: stop here until the user approves the plan.**

---

## Part 2: Scaffolding

Set up Docker, a minimal FastAPI backend and the start/stop scripts, serving a hello-world
page and one API call.

### Steps

- [x] Create `backend/` as a `uv` project (`pyproject.toml`, `uv.lock`) with FastAPI and
      an ASGI server (uvicorn).
- [x] Add `backend/app/main.py` with `GET /api/health` returning JSON (for example
      `{"status": "ok"}`).
- [x] Serve a placeholder static `index.html` at `/` that calls `/api/health` and shows
      the result.
- [x] Add a `Dockerfile` at the project root that installs dependencies with `uv` and runs
      the server on one exposed port (provisional: 8000).
- [x] Pass the root `.env` to the container at runtime (for example `--env-file .env`);
      do not copy it into the image. Add a `.dockerignore`.
- [x] Add `scripts/start.sh` and `scripts/stop.sh` (Mac and Linux) and `scripts/start.ps1`
      and `scripts/stop.ps1` (Windows) that build/run and stop/remove the container.
- [x] Add a backend test setup (pytest via `uv`) with a test for `/api/health`.
- [x] Update `backend/AGENTS.md` and `scripts/AGENTS.md`; keep the README minimal.

### Tests/Verification

- [x] `uv run pytest` in `backend/` passes (health JSON, root page contract, unknown
      `/api` route returns 404); `uv lock --check` passes.
- [x] `bash -n` passes for the shell scripts; the PowerShell parser reports no errors for
      the `.ps1` scripts.
- [x] Start script builds and runs the container; `http://localhost:8000/` shows the hello
      page with the health result; `curl http://localhost:8000/api/health` returns the JSON.
      Verified on Windows with `scripts/start.ps1` (Docker 29.8.2, `python:3.14-slim`).
- [x] Stop script stops and removes the container; re-running start works. Verified on
      Windows: stop removed the container, a second stop while absent exited successfully,
      restart served both routes again, and a final stop left no `pm-app` container.
- [x] Verify the scripts on the current platform; note any platform not verified.
      Windows verified. Mac and Linux runtime behavior is not verified; `start.sh` and
      `stop.sh` are syntax checked only.

### Success Criteria

- One command starts the app in Docker and one stops it.
- Static HTML and an API call both work from the same container.

---

## Part 3: Add in Frontend

Build the existing frontend statically and serve it from FastAPI at `/`.

### Steps

- [x] Configure Next.js for static export (`output: "export"`) without changing board
      behavior.
- [x] Add a Node build stage to the `Dockerfile` that runs `npm ci` and `npm run build`
      in `frontend/`, then copy the export into the Python stage.
- [x] Serve the exported files from FastAPI at `/`, keeping `/api/*` routes for the
      backend. Remove the Part 2 placeholder page.
- [x] Keep existing unit and E2E tests passing; extend tests so the served app is covered.
- [x] Add a backend test that `/` returns the built `index.html` (or a fixture) and
      `/api/health` still works.
- [x] Point Playwright at the containerized app (or document how to run against it) in
      addition to the dev server.
- [x] Update `frontend/AGENTS.md` for the new build and serving setup.

### Tests/Verification

- [x] `npm run lint`, `npm run test:unit` and `npm run build` pass in `frontend/`.
- [x] `uv run pytest` passes in `backend/`.
- [x] With the container running, Playwright E2E tests pass against `http://localhost:8000`:
      board loads with five columns, a card can be added and moved. Verified on Windows
      with `scripts/start.ps1`; Mac and Linux not verified.

### Success Criteria

- Starting the container shows the existing Kanban demo at `/` with unchanged behavior.
- No separate Node server is needed at runtime.

---

## Part 4: Add in a fake user sign in experience

Require the hardcoded login before showing the board, with logout.

### Steps

- [x] Add a login screen shown on first visit to `/` with username and password fields,
      styled with the project colors.
- [x] Validate credentials `user` / `password` on the backend:
      `POST /api/login` sets an HTTP-only session cookie; `POST /api/logout` clears it;
      `GET /api/me` reports the signed-in user.
- [x] Show the board only when signed in; show an error on wrong credentials.
- [x] Add a logout control on the board that returns to the login screen.
- [x] Keep credentials hardcoded for the MVP; do not add registration or password reset.
- [x] Add frontend unit tests, backend tests and E2E tests for the flow.

### Tests/Verification

- Backend tests: correct credentials succeed, wrong credentials fail, logout clears the
  session, protected checks reject anonymous requests.
- Frontend unit tests: login form renders, error state, board shown after sign in.
- E2E: visit `/` -> login screen; wrong password -> error; `user` / `password` -> board;
  logout -> login screen; reload while signed in keeps the session.

Verified on Windows against the real FastAPI server: 11 backend tests, 9 frontend unit
tests and 4 Chromium E2E tests pass; lint, static build and `uv lock --check` also pass.

### Success Criteria

- The board is not visible without signing in, and logout works.
- All existing and new tests pass against the running app.

---

## Part 5: Database modeling

Design the SQLite schema for users, boards, columns and cards, and get user sign-off.
Design only; no database code in this part.

### Steps

- [x] Propose a schema supporting multiple users with one board per user for the MVP,
      fixed renameable columns with order, and cards with title, details, column and
      position.
- [x] Save the schema as JSON in `docs/schema.json`.
- [x] Document the approach in `docs/DATABASE.md`: tables,
      relationships, ordering strategy, how the database file is created if missing,
      where it lives in the container, how the default board is seeded for a user, and
      how the board maps to the frontend `BoardData` shape.
- [x] Propose the API shape for Part 6 and how the Part 9 AI update will apply.
- [x] Present the design to the user.

### Tests/Verification

- The JSON file is valid JSON.
- The design can represent the current `initialData` board without loss.
- The document covers creation, seeding, ordering and multi-user support.

Verified in Part 5: `schema.json` parses as JSON; the relational mapping preserves every
field and ordering relationship in the current five-column, eight-card `initialData`; and
`DATABASE.md` covers creation, storage, seeding, ordering, API ownership and multi-user
isolation.

### Success Criteria

- The user has explicitly approved the schema and approach.

Approved by the user on 2026-10-15.

**Approval gate: stop here until the user approves the database design.**

---

## Part 6: Backend

Implement persistence and API routes for reading and changing a user's board, using the
approved Part 5 design.

### Steps

- [ ] Implement database setup that creates the SQLite file and tables if missing.
- [ ] Seed the default board (five columns, sample cards) for a user who has none.
- [ ] Implement the approved routes to read the board and change it: rename column, add,
      edit, move and delete cards.
- [ ] Scope all board routes to the signed-in user from Part 4; reject anonymous requests.
- [ ] Ensure the database file persists across container restarts (provisional: a
      mounted volume or bind mount set up by the start scripts).
- [ ] Write backend unit tests using a temporary database.
- [ ] Update `backend/AGENTS.md`.

### Tests/Verification

- `uv run pytest` passes, covering: database created when missing, seeding, each route's
  success path, invalid ids, anonymous rejection, and per-user isolation.
- Manual check in the container: change the board via the API, restart, data persists.

### Success Criteria

- The backend reads and changes a user's board in SQLite according to the approved design.
- Data survives a container restart.

---

## Part 7: Frontend + Backend

Make the frontend use the backend API so the board is persistent.

### Steps

- [ ] Load the board from the API after sign in instead of `initialData`.
- [ ] Persist column renames, card add, delete and move through the API.
- [ ] Add card editing (title and details), required by the business requirements and
      missing from the current demo, persisted through the API.
- [ ] Show a simple loading state and a simple error message on failed requests.
- [ ] Keep `moveCard` and other board logic pure and unit tested.
- [ ] Add frontend unit tests with a mocked API, and E2E tests against the container.
- [ ] Update `frontend/AGENTS.md`.

### Tests/Verification

- `npm run lint`, `npm run test:unit` and backend tests pass.
- E2E in the container: sign in, rename a column, add, edit, move and delete cards,
  reload the page and confirm every change persisted; restart the container and confirm
  again.

### Success Criteria

- The app is a persistent Kanban board for the signed-in user.
- All business requirements except AI chat are met.

---

## Part 8: AI connectivity

Allow the backend to call OpenRouter.

### Steps

- [ ] Add an OpenRouter client in the backend reading `OPENROUTER_API_KEY` from the
      environment and using model `openai/gpt-oss-120b`.
- [ ] Add a minimal backend route or function for a test prompt (provisional:
      `POST /api/ai/test`, signed-in only).
- [ ] Return a clear error when the key is missing or the call fails; never log the key.
- [ ] Add unit tests with the HTTP call mocked, and a separately runnable live test that
      asks "What is 2+2?".

### Tests/Verification

- Mocked unit tests pass without network access or a key.
- Live test in the container returns an answer containing 4.

### Success Criteria

- The backend makes a working AI call through OpenRouter with the configured model.

---

## Part 9: AI with board context and Structured Outputs

Send the board and conversation to the AI and receive a structured reply that may update
the board.

### Steps

- [ ] Add a chat route (provisional: `POST /api/ai/chat`) that takes the user's message
      and conversation history, loads the user's board JSON and sends both to the model.
- [ ] Define a Structured Outputs schema: a required reply message for the user and an
      optional board update (create, edit, move one or more cards; exact shape decided
      here based on the approved Part 5 design).
- [ ] Validate the AI output; apply a valid update to the database through the same
      logic as Part 6 routes; reject invalid updates without corrupting the board.
- [ ] Return the reply and whether the board changed (and the updated board if so).
- [ ] Keep conversation history client-supplied for the MVP unless Part 5 approved storing
      it.
- [ ] Add backend tests with a mocked model: reply only, single update, multi-card update,
      invalid output; plus a live test.

### Tests/Verification

- `uv run pytest` passes with mocked AI responses covering the cases above.
- Live test: asking the AI to add a card results in that card in the database.

### Success Criteria

- The AI answers with board context and can safely create, edit and move cards.

---

## Part 10: AI chat sidebar

Add a sidebar chat UI that uses the Part 9 route and refreshes the board on AI updates.

### Steps

- [ ] Add a sidebar chat widget alongside the board: message list, input, send button,
      styled with the project colors.
- [ ] Send messages and conversation history to the chat route; show the AI reply and a
      simple pending state.
- [ ] When the response reports a board change, refresh the board in the UI automatically.
- [ ] Show a simple error message when the AI call fails.
- [ ] Add frontend unit tests with a mocked API and E2E tests.
- [ ] Update `frontend/AGENTS.md` and keep the README minimal.

### Tests/Verification

- `npm run lint`, `npm run test:unit` and backend tests pass.
- E2E with a mocked AI route: send a message, see the reply, board updates without
  reload.
- Manual live check in the container: ask the AI to create and move a card and see the
  board update.

### Success Criteria

- A signed-in user can chat with the AI in the sidebar, and AI-driven board changes appear
  immediately and persist.
- All MVP business requirements in the root `AGENTS.md` are met.
