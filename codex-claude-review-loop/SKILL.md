---
name: codex-claude-review-loop
description: Review a repository, dispatch one bounded implementation task to an already-open writable Claude Code session through supervised Orca orchestration, and independently verify the delivery after worker_done. Use when Codex must act as reviewer and Claude Code as implementer. Do not use for unsupervised handoffs or when no existing Claude session is available.
---

# Codex-Claude Review Loop

Use this skill when Codex owns analysis, planning, acceptance and final reporting, while
Claude Code owns repository changes.

The workflow depends on Orca's `orca-cli` and `orchestration` capabilities. Read their
current, version-matched instructions before issuing Orca commands.

## Operating contract

- Codex reviews and plans; Claude Code implements.
- Keep exactly one bounded implementation task active in a shared worktree.
- Reuse an already-open, writable Claude Code terminal. Do not create a new session merely
  to avoid checking the existing one.
- Direct dispatch requires user authorization and a positively identified writable Claude
  session. Otherwise, provide a complete prompt for the user to copy.
- A request to edit the repository does not authorize commits, pushes, deployments,
  database mutations, credential changes or external-system writes unless separately stated.
- Preserve unrelated and pre-existing work.

## Review and dispatch

1. Read the repository guidance and inspect the current branch, status, staged and unstaged
   diffs, untracked files, relevant code, tests and recent commits.
2. Establish evidence before proposing work. Separate confirmed defects from hypotheses and
   planned behavior from behavior wired into the runtime.
3. Define one bounded Task with a stable identifier, objective, observed evidence, scope,
   likely files, constraints, acceptance criteria and relevant checks. Use
   [DISPATCH-TEMPLATE.md](DISPATCH-TEMPLATE.md).
4. Identify the existing Claude terminal through Orca and confirm it is connected, writable
   and belongs to the intended worktree.
5. Start a supervised Orca Task/Dispatch on that terminal. Include the exact `worker_done`
   completion contract from the template.
6. Once Orca reports the dispatch as accepted and the turn as started, end the Codex working
   turn immediately.

Do not keep a terminal wait open, poll or read Claude's terminal, stream its reasoning,
inspect partial edits or begin reviewing before `worker_done`. The callback is the completion
signal. This lets Claude work without an active Codex turn consuming tokens.

Live monitoring is allowed only when the user explicitly requests it or an already observed
condition requires immediate intervention to prevent an unauthorized or destructive action.

## Callback and verification

When `worker_done` reactivates Codex:

1. Treat the worker summary as an index, never as proof.
2. Inspect the current Git state and the actual diff, including untracked files and commits.
3. Re-read affected callers, contracts and failure paths.
4. Run checks proportional to risk and compare the evidence with every acceptance criterion.
5. Report each criterion as **met**, **unmet** or **not verified**.
6. If a correction is required, create a fresh bounded Task/Dispatch and repeat the same
   dispatch-and-callback cycle. Do not silently expand the original task.
7. After an accepted settlement, follow Orca's current instructions to reuse, retain or
   release worker ownership and acknowledge the delivery.

Use [REVIEW-CHECKLIST.md](REVIEW-CHECKLIST.md) for the delivery pass.

## Completion standard

Declare the task complete only when the repository evidence satisfies the acceptance
criteria and no required work remains. A green worker summary, elapsed time, terminal
silence or an idle prompt is not completion.
