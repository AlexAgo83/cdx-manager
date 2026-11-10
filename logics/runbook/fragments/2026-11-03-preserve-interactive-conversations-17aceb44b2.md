# Preserve interactive conversations — mission 17aceb44b2

## Incident and delivery

The reported 2026-11-03 remote test runs on Host B replaced the interactive
conversation IDs for the claw/grif profiles. Host A could not read the remote-only
transcripts despite having a recent local Claude interactive transcript.

Fresh Claude headless runs now receive a run-local conversation identity without
saving it to the profile. Run registry and history retain their conversation IDs.
Recording headless Codex history no longer observes a run transcript into the
interactive profile. Detached and continued runs follow the same rule; explicit
continuations still target their parent run's exact conversation.

`cdx conversation` first looks up the recorded session ID locally. If that ID
has no local transcript, it uses the existing recency resolver under the profile's
auth home. Explicit `--conversation` requests never fall back. The additive JSON
field `resolution_method` reports `conversation_id`, `recency`, or `null`.
Cursor identity checks still reject a cursor if resolution switches files.

## Conservative assumptions

The profile's stored ID may refer to another host. Do not delete or rewrite it
while reading a conversation and do not migrate real sessions.json data.
Recency is best effort, limited to the existing local resolver; it does not prove
that the newest transcript is interactive. Do not change resume, usage attribution,
authentication, deployment rules or shared operating/design documents.

No real remote inference or operator credential access is needed for this fix.
The fake worker regression exercises the remote launch path and then reads a
local interactive transcript; it is not a claim of production recovery.

## Validation

Every check runs through `.mission-input/mission-test-runner.py`; its unmodified
receipt in `.mission-artifacts/mission-tests.jsonl` records exact commands, exit
codes and durations. No UI changes or screenshots are needed. There is no
separate typecheck script; the project lint includes Python compilation.

The initial baseline inherited sandbox Git overrides and RTK_DB_PATH, causing
unrelated temporary-repository and fake-RTK failures. The system Python also
lacked Ruff and Cargo was absent. Install frozen Python development dependencies
and public Rust tooling, then run checks with the virtual environment on PATH.
Only test subprocesses clear GIT_DIR, GIT_COMMON_DIR, GIT_WORK_TREE and RTK_DB_PATH;
mission repository Git remains read-only. A rescue fixture that used the old
run identity helper to simulate an interactive session now uses launch_session.

Checks cover missing recorded IDs, missing explicit IDs, exact local resolution,
latest local transcript selection for all structured providers, a remote Claude
run followed by local interactive reading, detached Claude identity preservation,
Claude/Codex continuations, and Codex run-history versus interactive observation.

Final verification results:

- `npm run lint`: passed, including documentation checks and Python compilation.
- `npm test`: 1544 passed, 4 skipped (opt-in sandbox acceptance), 3 existing
  Python deprecation warnings; the final run uses the prepared environment above.
- `cargo test --manifest-path tray/Cargo.toml`: 99 passed after public Rust setup;
  two existing dead-code warnings remain.
- `npm pack --dry-run`: passed.
- `uv build --out-dir .mission-artifacts/dist`: source distribution and wheel built.
- Targeted reader/run/remote/rescue checks: passed after the fixture correction.
- `logics-manager lint --require-status`: passed.
- `logics-manager audit --group-by-doc`: passed with six existing warnings in
  unrelated agent-state and detached-failover documents.

Human review should check the additive JSON field, the best-effort recency
semantics and run-history identity preservation. Cross-platform CI remains the
final merge gate. No production host measurement is required for acceptance.
