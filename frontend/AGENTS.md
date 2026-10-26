# Frontend

This describes the frontend as it exists today. It has a backend-authenticated sign-in gate
around an in-memory Kanban board, with no persistence or AI. It is built as a static export
and served by the FastAPI backend at `/`. Planned changes are tracked in `docs/PLAN.md`.

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
    KanbanBoard.tsx      Client component; owns board state and the DndContext
    KanbanColumn.tsx     Droppable column, editable title input, card list, new-card form
    KanbanCard.tsx       Sortable card with a Remove button
    KanbanCardPreview.tsx  Static card used in the DragOverlay
    NewCardForm.tsx      Toggleable form for title + details
    AuthenticatedApp.test.tsx  Authentication component tests
    KanbanBoard.test.tsx Component tests
  lib/
    kanban.ts            Types, initialData, moveCard, createId
    kanban.test.ts       moveCard unit tests
  test/
    setup.ts             Loads jest-dom matchers
    vitest.d.ts          Type references for Vitest globals and jest-dom
tests/
  kanban.spec.ts         Playwright E2E tests
```

`public/` holds only the default Next.js SVGs, which are unused.

## Data model (`src/lib/kanban.ts`)

- `Card { id, title, details }`
- `Column { id, title, cardIds: string[] }`
- `BoardData { columns: Column[]; cards: Record<string, Card> }`
- `initialData`: five columns (`col-backlog`, `col-discovery`, `col-progress`,
  `col-review`, `col-done`) and eight sample cards (`card-1` to `card-8`).
- `moveCard(columns, activeId, overId)`: pure function returning new columns. Handles
  reorder within a column, move to another column before a target card, and drop onto a
  column (appends to the end). Returns the input unchanged for unknown ids.
- `createId(prefix)`: random + timestamp id, e.g. `card-xxxxxx...`.

## State and data flow

- `AuthenticatedApp` calls `GET /api/me` on load. Anonymous visitors see the login form;
  authenticated visitors see `KanbanBoard`. Login and logout use the backend's HTTP-only
  session cookie, so the browser restores a valid session after reload.
- All state lives in `KanbanBoard` via `useState<BoardData>(initialData)`. There is no
  board API or storage; a page reload resets the board.
- Handlers in `KanbanBoard` (`handleRenameColumn`, `handleAddCard`, `handleDeleteCard`,
  `handleDragEnd`) update state immutably and are passed down as props.
- Drag and drop: `DndContext` with `PointerSensor` (6px activation distance) and
  `closestCorners`. Each column is a `useDroppable` target and wraps its cards in a
  `SortableContext`; each card uses `useSortable`. `onDragEnd` calls `moveCard`.
  `DragOverlay` renders `KanbanCardPreview` for the active card.

## Current behavior

- First visit shows a sign-in screen. The hardcoded credentials are `user` / `password`;
  invalid credentials show an inline error.
- A valid session shows the board. The header displays the username and a logout button.
- Header with title, tagline and a pill per column showing the live column title.
- Five fixed columns. Column titles are renamed inline through an input
  (`aria-label="Column title"`), updated on every keystroke. Columns cannot be added,
  removed or reordered.
- Each column shows its card count and a "Drop a card here" placeholder when empty.
- Add card: "Add a card" opens a form; title is required (trimmed), empty details become
  "No details yet.". New cards append to the column.
- Delete card: "Remove" button (`aria-label="Delete <title>"`).
- Move cards by drag and drop within and across columns.
- Existing cards cannot be edited (no title/details edit UI).

## Commands

Run from `frontend/`:

- `npm install`
- `npm run dev` - dev server on port 3000
- `npm run build` - static export to `out/`
- `npm run lint`
- `npm run test` or `npm run test:unit` - Vitest once; `npm run test:unit:watch` - watch
- `npm run test:e2e` - installs the required Chromium build, then runs Playwright; starts
  `npm run dev` on `127.0.0.1:3000` or reuses an existing server
- E2E against the running container: set `PLAYWRIGHT_BASE_URL=http://localhost:8000`
  (PowerShell: `$env:PLAYWRIGHT_BASE_URL = "http://localhost:8000"`) and run
  `npm run test:e2e`; no dev server is started
- `npm run test:all` - unit then E2E

## Tests

- `src/lib/kanban.test.ts`: `moveCard` reorder in same column, move to another column,
  drop on column end.
- `src/components/KanbanBoard.test.tsx`: renders five columns, renames a column, adds and
  removes a card.
- `src/components/AuthenticatedApp.test.tsx`: anonymous login screen, invalid credentials,
  successful login and logout.
- `tests/kanban.spec.ts`: complete sign-in/session/logout flow, board load, add card and
  drag `card-1` into `col-review`. It mocks auth for the standalone Next.js dev server and
  uses the real API when `PLAYWRIGHT_BASE_URL` is set.
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

- Authentication is the only backend integration; the board is not yet persistent and
  there is no AI chat.
- Single hardcoded board from `initialData`; state resets on reload.
- No card editing.
- Static export only: no server-side rendering, route handlers or Next.js server features.
- `next/font/google` fetches fonts at build time, so builds need network access.
- Drag and drop supports pointer input only (no keyboard sensor).
