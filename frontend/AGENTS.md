# Frontend

This describes the frontend as it exists today. It has a backend-authenticated sign-in gate
around a Kanban board persisted through the FastAPI board API, with no AI yet. It is built
as a static export and served by the FastAPI backend at `/`. Planned changes are tracked in
`docs/PLAN.md`.

## Build and serving

- `next.config.ts` sets `output: "export"`; `npm run build` writes static files to `out/`
  (gitignored). There is no Node server at runtime, so `npm run start` does not apply.
- The root `Dockerfile` builds the frontend in a Node stage (`npm ci`, `npm run build`) and
  copies `out/` to `/app/static` in the Python image, where FastAPI serves it.
- Locally, the backend serves `frontend/out` if it exists (see `backend/AGENTS.md`).

## Stack

- Next.js 16.1.6 (App Router), React 19.2.3, TypeScript (strict)
- Tailwind CSS 4 via `@tailwindcss/postcss`; theme tokens in `src/app/globals.css`
- `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities` for drag and drop
- `clsx` for conditional class names
- Fonts: Space Grotesk (display) and Manrope (body) via `next/font/google`
- Unit tests: Vitest 3 + jsdom + Testing Library (`@testing-library/react`, `user-event`,
  `jest-dom`)
- E2E tests: Playwright (Chromium only)
- Lint: ESLint 9 with `eslint-config-next` (core-web-vitals and typescript)

## Layout

```
src/
  app/
    layout.tsx           Root layout, fonts, metadata ("Kanban Studio")
    page.tsx             Home route; renders <AuthenticatedApp />
    globals.css          Tailwind import, color/surface CSS variables, base styles
  components/
    AuthenticatedApp.tsx Login/session gate; calls /api/me, /api/login and /api/logout
    KanbanBoard.tsx      Client component; loads the board, saves changes, owns the DndContext
    KanbanColumn.tsx     Droppable column, title draft input, card list, new-card form
    KanbanCard.tsx       Sortable card with inline Edit form and a Remove button
    KanbanCardPreview.tsx  Static card used in the DragOverlay
    NewCardForm.tsx      Toggleable form for title + details
    AuthenticatedApp.test.tsx  Authentication component tests (fetch mocked)
    KanbanBoard.test.tsx Board component tests (fetch mocked)
  lib/
    api.ts               Typed board API client (boardApi) and ApiError
    kanban.ts            Types, initialData, moveCard, planMove
    kanban.test.ts       moveCard and planMove unit tests
  test/
    setup.ts             Loads jest-dom matchers
    vitest.d.ts          Type references for Vitest globals and jest-dom
tests/
  kanban.spec.ts         Playwright E2E tests
  mockApi.ts             Stateful mock of the auth and board API for the dev server
```

`public/` holds only the default Next.js SVGs, which are unused.

## Data model (`src/lib/kanban.ts`)

- `Card { id, title, details }`
- `Column { id, title, cardIds: string[] }`
- `BoardData { columns: Column[]; cards: Record<string, Card> }`
- `initialData`: five columns (`col-backlog`, `col-discovery`, `col-progress`,
  `col-review`, `col-done`) and eight sample cards (`card-1` to `card-8`). It matches the
  backend seed and is used as a test fixture; the app no longer renders it directly.
- `moveCard(columns, activeId, overId)`: pure function returning new columns. Handles
  reorder within a column, move to another column before a target card, and drop onto a
  column (appends to the end). Returns the input unchanged for unknown ids.
- `planMove(columns, activeId, overId)`: uses `moveCard` and returns the final columns plus
  the move API arguments (`columnId` and the zero-based `position` in that column's final
  list), or `null` for a no-op drop.

## State and data flow

- `AuthenticatedApp` calls `GET /api/me` on load. Anonymous visitors see the login form;
  authenticated visitors see `KanbanBoard`. Login and logout use the backend's HTTP-only
  session cookie, so the browser restores a valid session after reload.
- `KanbanBoard` loads `GET /api/board` on mount ("Loading board..." until it arrives).
  `src/lib/api.ts` wraps the Part 6 routes: `PATCH /api/columns/{id}`, `POST /api/cards`,
  `PATCH /api/cards/{id}`, `POST /api/cards/{id}/move` and `DELETE /api/cards/{id}`.
- Every change goes through `save()`: the full `BoardData` returned by the server replaces
  local state. If a request fails, the board is reloaded from the server and one error
  banner (`role="alert"`) is shown with a "Reload board" button. A failed initial load
  shows the same banner instead of the board.
- Handlers return `Promise<boolean>` so forms stay open (new card, card edit) or the column
  title restores its server value when saving fails.
- Drag and drop: `DndContext` with `PointerSensor` (6px activation distance) and
  `closestCorners`. Each column is a `useDroppable` target and wraps its cards in a
  `SortableContext`; each card uses `useSortable`. `onDragEnd` calls `planMove`, shows the
  planned columns immediately, sends the move and then accepts the server board.
  `DragOverlay` renders `KanbanCardPreview` for the active card.

## Current behavior

- First visit shows a sign-in screen. The hardcoded credentials are `user` / `password`;
  invalid credentials show an inline error.
- A valid session shows the board. The header displays the username and a logout button.
- Header with title, tagline and a pill per column showing the live column title.
- Five fixed columns. Column titles are edited inline through an input
  (`aria-label="Column title"`) that keeps a local draft and saves a changed, trimmed,
  non-empty title on blur or Enter. An empty or unchanged title restores the saved value.
  Columns cannot be added, removed or reordered.
- Each column shows its card count and a "Drop a card here" placeholder when empty.
- Add card: "Add a card" opens a form; title is required (trimmed), details are trimmed and
  may be empty. New cards append to the column.
- Edit card: "Edit" (`aria-label="Edit <title>"`) opens an inline form with "Card title"
  and "Card details" fields and Save/Cancel. Title is required (trimmed); details may be
  empty. Dragging is disabled while a card is being edited.
- Delete card: "Remove" button (`aria-label="Delete <title>"`).
- Move cards by drag and drop within and across columns.
- All changes persist for the signed-in user.

## Commands

Run from `frontend/`:

- `npm install`
- `npm run dev` - dev server on port 3000
- `npm run build` - static export to `out/`
- `npm run lint`
- `npm run test` or `npm run test:unit` - Vitest once; `npm run test:unit:watch` - watch
- `npm run test:e2e` - installs the required Chromium build, then runs Playwright; starts
  `npm run dev` on `127.0.0.1:3000` or reuses an existing server
- E2E against the running container: set `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8000`
  (PowerShell: `$env:PLAYWRIGHT_BASE_URL = "http://127.0.0.1:8000"`) and run
  `npm run test:e2e`; no dev server is started and the real API and database are used.
  Optionally set `E2E_RESTART_COMMAND` to a shell command that restarts the container
  (Windows example: `powershell -NoProfile -File ..\scripts\stop.ps1 && powershell
  -NoProfile -File ..\scripts\start.ps1`) to also verify persistence across a restart
- `npm run test:all` - unit then E2E

## Tests

- `src/lib/kanban.test.ts`: `moveCard` reorder in same column, move to another column,
  drop on column end; `planMove` request mapping for reorder, cross-column, column drop
  and no-op.
- `src/components/KanbanBoard.test.tsx` (fetch mocked): loading state and board load, load
  failure and reload, column rename on blur/Enter with trimming, no request for an empty
  or unchanged title, rename failure restore, add card request and result, add failure
  keeps the form, inline edit request and result, empty edit title and Cancel, delete,
  mutation failure reloads the server board.
- `src/components/AuthenticatedApp.test.tsx`: anonymous login screen, invalid credentials,
  successful login with board fetch, logout.
- `tests/kanban.spec.ts`: sign-in/session/logout flow, board load, and a persistence test
  that renames `col-discovery`, adds two uniquely named cards, edits one, drags it into
  `col-review`, deletes the other, reloads and verifies (and, with `E2E_RESTART_COMMAND`,
  restarts the container and verifies again). Against the standalone dev server it uses
  the stateful mock in `tests/mockApi.ts`; with `PLAYWRIGHT_BASE_URL` it uses the real API
  and finally deletes its cards and restores the column title.
- Vitest includes `src/**/*.{test,spec}.{ts,tsx}` and excludes `tests/`. Coverage is
  available through `@vitest/coverage-v8` (text and html reporters) but no threshold is set.
- Selectors rely on `data-testid` values `column-<columnId>` and `card-<cardId>`, plus
  accessible labels and placeholders. Keep them stable or update tests together.
- `test-results/.last-run.json` is a tracked Playwright artifact.

## Conventions

- Named exports for components (`export const X = () => ...`); `@/` alias maps to `src/`.
- `AuthenticatedApp.tsx` and `KanbanBoard.tsx` are client components; their children run
  inside them.
- Styling is Tailwind utility classes referencing CSS variables
  (`var(--navy-dark)`, `var(--primary-blue)`, `var(--secondary-purple)`,
  `var(--accent-yellow)`, `var(--gray-text)`, `var(--stroke)`, `var(--shadow)`). Use these
  tokens rather than new hex values.
- Keep board logic pure in `src/lib/kanban.ts` and unit test it there.
- Keep components small, no extra features, no emojis.

## Limitations

- No AI chat yet.
- One board per user; columns are fixed (rename only).
- Static export only: no server-side rendering, route handlers or Next.js server features.
- `next/font/google` fetches fonts at build time, so builds need network access.
- Drag and drop supports pointer input only (no keyboard sensor).
