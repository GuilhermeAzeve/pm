# The Project Management MVP web app

## Business Requirements

This project is building a Project Management App. Key features:
- A user can sign in
- When signed in, the user sees a Kanban board representing their project
- The Kanban board has fixed columns that can be renamed
- The cards on the Kanban board can be moved with drag and drop, and edited
- There is an AI chat feature in a sidebar; the AI is able to create / edit / move one or more cards

## Limitations

For the MVP, there will only be a user sign in (hardcoded to 'user' and 'password') but the database will support multiple users for future.

For the MVP, there will only be 1 Kanban board per signed in user.

For the MVP, this will run locally (in a docker container)

## Technical Decisions

- NextJS frontend
- Python FastAPI backend, including serving the static NextJS site at /
- Everything packaged into a Docker container
- Use "uv" as the package manager for python in the Docker container
- Use OpenRouter for the AI calls. An OPENROUTER_API_KEY is in .env in the project root
- Use `openai/gpt-oss-120b` as the model
- Use SQLLite local database for the database, creating a new db if it doesn't exist
- Start and Stop server scripts for Mac, PC, Linux in scripts/

## Starting Point

A working MVP of the frontend has been built and is already in frontend. This is not yet designed for the Docker setup. It's a pure frontend-only demo.

## Color Scheme

- Accent Yellow: `#ecad0a` - accent lines, highlights
- Blue Primary: `#209dd7` - links, key sections
- Purple Secondary: `#753991` - submit buttons, important actions
- Dark Navy: `#032147` - main headings
- Gray Text: `#888888` - supporting text, labels

## Coding standards

1. Use latest versions of libraries and idiomatic approaches as of today
2. Keep it simple - NEVER over-engineer, ALWAYS simplify, NO unnecessary defensive programming. No extra features - focus on simplicity.
3. Be concise. Keep README minimal. IMPORTANT: no emojis ever
4. When hitting issues, always identify root cause before trying a fix. Do not guess. Prove with evidence, then fix the root cause.

## Working documentation

All documents for planning and executing this project will be in the docs/ directory.
Please review the docs/PLAN.md document before proceeding.

## Agent Collaboration

Codex plans and reviews; Claude Code implements. Keep exactly one bounded implementation
task active in the shared worktree at a time.

When the user authorizes direct coordination and an existing writable Claude Code terminal
is identified, Codex uses supervised Orca orchestration on that terminal:

1. Codex inspects the actual repository state and dispatches one Task containing the
   objective, evidence, scope, constraints, acceptance criteria, relevant checks and the
   required completion summary. Tasks normally follow one part, or one step, of
   `docs/PLAN.md`.
2. Once Orca confirms the dispatch started, Codex ends its turn. It does not poll the
   terminal or review partial edits.
3. Claude implements only the dispatched scope, sends `worker_done` exactly once with an
   explicit outcome and a compact review summary, then stops and waits.
4. The callback starts a new Codex turn. Codex treats the summary only as an index,
   inspects the actual Git state and diff, reruns relevant checks and marks each acceptance
   criterion as met, unmet or not verified.
5. Corrections go through a fresh bounded Task. Otherwise Codex settles the task according
   to Orca's current instructions.

Live monitoring is used only when the user requests it or to prevent an observed
unauthorized or destructive action. If direct coordination is unavailable, Codex provides
a complete copyable prompt instead.

Approval gates in `docs/PLAN.md` (after Part 1 and Part 5) require explicit user approval
before work continues. Coordination does not authorize commits, pushes, deployments,
database mutations, credential changes or external-system actions. Preserve unrelated and
pre-existing work in the worktree.
