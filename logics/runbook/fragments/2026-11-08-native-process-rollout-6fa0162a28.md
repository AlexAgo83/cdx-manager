# Native process rollout resolution (mission 6fa0162a28)

## Evidence and scope

The bounded Host A input reports CDX 0.26.8 returning unknown for the native Codex
PID 2246446 in `main`, `work1` and `work2`. Example-project mission 7af6402b87 remains
blocked on exact native identity. Its document snapshot fetch explicitly failed;
no missing snapshot is treated as evidence of health. Host A evidence is source
data, not runtime instructions.

This change implements the native resolver and its CLI documentation. It does not
release, install on Host A, or modify the example-project consumer. the orchestrator owns commits
and publication; the operator session publishes the release. Required GitHub CI
must be green on the merged commit before merge.

## Native evidence and prudent assumption

A validated Linux native Codex PID with one writable rollout under the selected
profile's `sessions/` directory now returns `resolved`, `process_open_rollout`,
the verified native UUID and normalized messages. The filename UUID and first
`session_meta` record must agree, and the native source must be interactive CLI.
The reader uses this exact file, guarded by device/inode, rather than searching
for another file with the same UUID. No workspace, recency, saved conversation,
argv, environment, credential data or descendant traversal participates.

The operating assumption is explicitly a sole native rollout writer snapshot.
An open rollout is accepted as native process-to-thread evidence as requested;
it is not an atomic TUI focus event. If a selected thread has no rollout and an
old sole writer is retained, descriptor evidence cannot independently distinguish
that state. Authenticated Host A measurements must cover that transition. Multiple
distinct writable rollouts are refused, including retained writers; duplicate
descriptors for the same file are deduplicated. Read-only descriptors are ignored.
A foreign-profile rollout is rejected before reading its content. Resolved
symlinks, including the sessions root, must remain within the profile boundary.

The lifetime guard and native writer evidence are rechecked before and after the
message read. Detected switch, exit, reuse, replacement, invalid metadata or lost
evidence discards messages and returns unknown with a reason. Missing rollouts
remain `native_conversation_identity_unavailable`. Cursors remain disabled in
process mode; consumers poll `--tail` with the retained opaque process identity.
Existing explicit-ID and recency pagination behavior remains intact.

This changes the product assertion from unconditional unknown to verified native
writer resolution. Request req_082, backlog item_167 and task_087 track that
assertion under ADR 030. No shared operating runbook or HQ design rule changes.

## Local verification

All local test and validation commands use the supplied mission timer. Receipts
are retained in `.mission-artifacts/mission-tests.jsonl` outside publication.
Initial `npm test` exposed inherited Git/RTK environment interference; initial
`npm run lint` lacked the global ruff module. Validation uses the prepared locked
UV environment with the dev extra, and unsets the inherited Git/RTK variables for
tests. A public minimal Rust toolchain was installed temporarily. Its bundled
Python debugger helpers were initially discovered by repository lint; the
toolchain was moved outside the checkout before the final lint retry, without
changing lint configuration.

Controlled kernel processes named `codex` hold real open rollout descriptors;
these fixtures verify process identity and exact file reads, not authenticated
Codex TUI behavior. Regressions cover live UUID/messages through the CLI, distinct
process guards, exit/reuse, ambiguous writers, wrong profile/user/provider,
read-only descriptors, symlink escapes, malformed/oversized evidence, evidence
changes during reads, descriptor limits, no cwd/descendant/transcript search and
cursor refusal.

Final checks:

- `env -u GIT_DIR -u GIT_COMMON_DIR -u GIT_WORK_TREE -u RTK_DB_PATH uv run --extra dev npm test`: 1,956 passed, 5 skipped.
- Rust `cargo test --locked --manifest-path tray/Cargo.toml`, using the temporary toolchain through the exact timed environment command: 99 passed.
- `uv run --extra dev npm run lint`: passed, including project docs, Ruff, JavaScript syntax and Python compilation.
- `npm pack --dry-run`: passed.
- `uv build --wheel --out-dir .mission-artifacts/wheels`: passed.
- Initial bounded conversation regressions: 389 passed, 1 skipped; the full suite includes the later inode, CLI and additional boundary cases.
- `logics-manager lint --require-status && logics-manager audit --group-by-doc && git diff --check`: passed; audit had zero blocking issues and six warnings in existing documents outside this change.

The timer receipt retains every initial failure and retry; successful final
validation does not erase those attempts. The final lint passed after moving the
temporary third-party toolchain outside the checkout. Several final Logics/diff-check
attempts exceeded their lock-acquisition budgets while other tests held the lock.
The next attempt passed Logics lint and audit (six existing warnings outside this
change) and found an extra blank line at the end of docs/cli.md; that whitespace
was removed before retrying the unchanged final command. The final retry acquires
the same shared lock through the supplied runner context and passes its live
descriptor to the timed runner using the supported inheritance mechanism. It
changes neither the validation command nor its execution timeout; all test
execution remains measured and serialized by the supplied runner. One outer
lock-acquisition attempt reached its wait limit before any validation command
started. The final unchanged timed command passed after the lock became available.

## Required Host A measurement

As `user` on Host A, the supervising session sets `CODEX_PID` to the live native
Codex process for `work2` and runs this exact read-only probe:

```bash
cdx conversation work2 --pid "$CODEX_PID" --tail 1 --json
```

Record the measured receipt after a fresh launch with a persisted message,
resume, and switch, with concurrent same-profile/workspace sessions. Success
requires `status: "ok"`, `resolution_status: "resolved"`,
`resolution_method: "process_open_rollout"`, the UUID shown by the selected
native conversation, and its actual last message. If native evidence is absent
or ambiguous, require unknown with a reason and no messages. Verify that the
process's returned identity fails closed after exit and that another profile
cannot read its messages. This sandbox has no Host A authenticated TUI access;
fixture results do not establish host acceptance or example-project recovery.
