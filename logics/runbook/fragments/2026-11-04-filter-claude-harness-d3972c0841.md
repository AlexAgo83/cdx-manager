# Filter Claude harness records — mission d3972c0841

## Change and conservative assumptions

The Claude conversation reader now removes complete, anchored harness text
blocks for task notifications, local command stdout/stderr, command name/message/
args, and system reminders. Prose before, after, or between complete wrappers
remains user content. Tool results retain their existing handling.

Mid-turn messages are unwrapped only when the first text block starts with the
reported Claude Code prefix and the last text block ends with the reported
explanatory line and closing instruction. The explanatory line must stay on one
line; unfamiliar or incomplete wrappers remain visible rather than risking loss
of operator content. Text can span multiple blocks around image blocks.

The existing entry schema has no image field. Normal and wrapped Claude user
records containing only an image therefore retain an empty-text user entry;
image source data is never returned. This is the conservative interpretation of
preserving image-bearing records without introducing an attachment API.

Under ADR 030 this is a local parser correction whose reasoning is captured at
the parser and in regression tests; it needs no workflow chain. Cursor encoding,
offsets, record IDs, and paging algorithms are unchanged. No shared operating or
design rule changes, UI edits, screenshots, or host measurements are required.

## Verification

All local checks use `.jarvis-input/mission-test-runner.py` with each complete
command supplied as one argument. Exact timings and exit codes are recorded in
`.jarvis-artifacts/mission-tests.jsonl`; receipts are not edited.

The baseline `npm test` encountered four failures and two setup errors caused by
inherited Git overrides and RTK_DB_PATH in tests creating temporary repositories
or simulating RTK history. The baseline `npm run lint` could not import Ruff.
After `uv sync --frozen --extra dev`, checks use the development virtualenv on
PATH. Full-suite subprocesses clear GIT_DIR, GIT_COMMON_DIR, GIT_WORK_TREE, and
RTK_DB_PATH; repository Git protections are unchanged. Rust was installed from
the public Rustup distribution because Cargo was absent.

- `npm run lint`: passed after installing development dependencies; includes
  documentation checks, Ruff, Node syntax checks, and Python compilation.
- `python -m pytest test/test_conversation_py.py test/test_commands_conversation_py.py`:
  passed, 340 tests and one skipped, before the final three edge-case fixtures.
- `npm test`: final run passed after isolating test environment overrides,
  with 1836 passed, five opt-in skips, and three existing deprecation warnings.
- `cargo test --manifest-path tray/Cargo.toml`: passed, 99 tests; two existing
  dead-code warnings. Cargo uses its installed bin directory on PATH.
- `uv build --out-dir .jarvis-artifacts/dist`: passed, source distribution and wheel.
- `npm pack --dry-run`: passed.
- `logics-manager lint --require-status`: passed.
- `logics-manager audit --group-by-doc`: passed with six existing warnings in
  unrelated agent-state and detached-failover documents.
- `git diff --check`: passed.

There is no separate typecheck script. New sanitized JSONL fixtures cover task
and monitor notifications, every command wrapper, multiple text blocks, text
and image mid-turn messages, image-only messages, empty wrappers, ordinary
quoted markup, incomplete wrappers, and prose between tags. Paging regression
compares forward pages, tail/before pages, IDs, and exhausted cursor resumes.

Human review should check the anchored wrapper grammar against the reported
Claude Code transcript shape and the empty-text representation for image-only
messages. Cross-platform GitHub CI remains the merge gate.
