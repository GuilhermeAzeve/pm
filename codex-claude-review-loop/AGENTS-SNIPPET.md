# Agent Collaboration

Claude Code implements repository changes. Codex reviews the current repository, defines
one bounded implementation task at a time and independently verifies each delivery.

When the user authorizes direct coordination and an existing writable Claude Code session
is identified, Codex uses supervised Orca orchestration on that terminal:

1. Codex inspects the actual repository state and creates one Task/Dispatch containing the
   objective, evidence, scope, constraints, acceptance criteria, relevant checks and the
   required completion summary.
2. After Orca confirms that the dispatch was accepted and the Claude turn started, Codex
   ends its working turn. It does not poll the terminal, stream intermediate reasoning or
   review partial edits.
3. Claude implements only the dispatched scope and sends `worker_done` exactly once with an
   explicit outcome and compact review summary. Claude then stops and waits.
4. The callback starts a new Codex working turn. Codex treats the summary only as an index,
   inspects the actual Git state and diff, reruns relevant checks and marks every acceptance
   criterion as met, unmet or not verified.
5. If a correction is required, Codex creates a fresh bounded Task/Dispatch and repeats the
   cycle. Otherwise, it settles worker ownership according to Orca's current instructions.

Live monitoring is an exception only when the user explicitly requests it or when an
already observed condition requires immediate intervention to prevent an unauthorized or
destructive action.

If direct coordination is unavailable, Codex provides a complete copyable prompt instead.
Direct coordination does not authorize commits, pushes, releases, deployments, database
mutations, credential changes or external-system actions without the permission required
for that action. Preserve unrelated and pre-existing work in the shared worktree.
