# Task/Dispatch Template

```text
IDENTIFIER: <stable-task-id>

OBJECTIVE
<One concrete result. Keep the task bounded.>

OBSERVED CONTEXT
- <Confirmed evidence with file:line, command output or reproduction.>
- <Current Git/worktree facts relevant to attribution.>

SCOPE
- <Behavior or component included.>
- <Likely files or boundaries.>

EXPECTED BEHAVIOR
1. <Observable behavior after the change.>
2. <Important failure, retry or compatibility behavior.>

CONSTRAINTS
- Preserve unrelated and pre-existing work.
- Do not broaden the objective or change external systems.
- Do not commit, push, deploy, mutate databases, change credentials or perform other
  externally consequential actions unless this Task explicitly authorizes them.
- Follow the repository's own guidance and conventions.

ACCEPTANCE CRITERIA
- <Criterion with observable evidence.>
- <Regression or failure-path criterion.>
- <Git scope criterion: only intended files changed.>

RELEVANT CHECKS
- <Focused test or validation command.>
- <Lint, type, format or integration check appropriate to the risk.>

COMPLETION CONTRACT
When finished, send worker_done exactly once with an explicit outcome and a compact
REVIEW SUMMARY FOR CODEX: objective completed; files changed; important decisions;
tests/commands run and results; acceptance criteria satisfied; limitations, pending items
or risks; Git and commit state. Then end your turn and wait for Codex review.
```

If multiple solutions are reasonable, describe the decision criteria rather than forcing
an implementation detail. If input, authorization or a decision is missing, Claude must use
the orchestration question or escalation mechanism so Codex is reactivated with the blocker.
