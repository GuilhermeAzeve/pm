# Delivery Review Checklist

## Establish the baseline

- Confirm the callback belongs to the expected Task and active Dispatch.
- Inspect branch, `git status`, staged and unstaged diffs, untracked files and recent commits.
- Attribute changes from repository evidence, not from the worker summary.

## Review the implementation

- Compare the actual behavior with every acceptance criterion.
- Trace affected callers, state transitions, persistence boundaries and error paths.
- Check compatibility, retries, idempotency, recovery, partial failures, security and data
  integrity when relevant to the task.
- Confirm unrelated work was preserved and the diff stayed within scope.
- Run focused tests first, then broader checks when the risk warrants them.
- Record environmental checks that were skipped or could not be verified.

## Classify the result

For every acceptance criterion, use exactly one status:

- **Met**: supported by code, diff or executed verification.
- **Unmet**: evidence shows the required behavior is absent or incorrect.
- **Not verified**: verification needs an unavailable environment, permission or dependency.

Do not turn `not verified` into success and do not treat a skipped environmental check as a
confirmed defect.

## Settle the cycle

- If all required criteria are met, report completion and settle worker ownership using the
  current Orca orchestration instructions.
- If correction is needed, define a new bounded Task/Dispatch with fresh evidence and repeat
  the callback cycle.
- If new authority or a material scope decision is required, stop and ask the user instead
  of assuming permission.
