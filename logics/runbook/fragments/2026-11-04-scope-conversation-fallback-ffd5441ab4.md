# Scope conversation fallback — mission ffd5441ab4

## Incident and change

On 2026-11-04 at 00:39, a new grif interactive session in the cts project
was awaiting folder trust. With no transcript yet, the conversation reader
selected the newest transcript across the profile, from remote-ops.

For release 0.26.2, conversation recency fallback now uses `--cwd PATH`, or the
process working directory when omitted. Claude-compatible providers scan only
`.claude/projects/<path-slug>` using the existing project-name helper. Codex
requires the same canonical directory in the initial `session_meta.cwd` record;
unreadable, missing, malformed or relative metadata is excluded. Metadata reads
are bounded to 64 KiB. Subagent folders are excluded from scoped scans.

`--since ISO` is passed through both fallback paths, including when a stored
conversation ID has no local file. No candidate produces `unavailable` with
`no_conversation_yet`. `resolution_method` retains its existing values;
`resolution_scope` records canonical `cwd` and supplied `since` for fallback
attempts, including absence. Exact lookups and unsupported providers have a
null scope. Exact IDs retain their existing lookup and absence semantics.

## Conservative assumptions

The time filter uses transcript modification time, matching the existing
resolver's session-start cutoff, and includes the exact cutoff. Callers should
supply a timezone in the ISO timestamp. Without `--since`, recency can still
select an earlier conversation in the same project. This remains a best-effort
fallback and cannot identify simultaneous sessions in the same directory.

Exact conversation IDs remain authoritative. Profile state is never rewritten.
Usage attribution callers do not opt into the new project filter. Claude paths
that cannot be represented by the existing slug helper produce absence rather
than a profile-wide guess. There is no hub implementation in this repository;
the CLI contract supports the hub's panel working directory and session start.

Under ADR 030 this is a bounded resolver correction: its reasoning lives beside
the resolver and its regression tests; no new workflow chain is needed. Shared
operating and design documents do not change. No UI or screenshots are needed.

## Validation

Every local check runs through `.jarvis-input/mission-test-runner.py`; exact
commands, exit codes and measured durations are retained in
`.jarvis-artifacts/mission-tests.jsonl` without editing the receipt.

The first baseline `npm test` inherited mission Git overrides and RTK_DB_PATH:
four tests failed and two setup errors occurred in unrelated temporary-repo and
RTK tests. The first `npm run lint` could not import Ruff. Frozen development
dependencies were installed; subsequent test subprocesses clear GIT_DIR,
GIT_COMMON_DIR, GIT_WORK_TREE and RTK_DB_PATH. Repository Git remains read-only.
Rust tooling was installed publicly because Cargo was absent.

Regression coverage includes two projects sharing a profile, an empty project
awaiting trust, implicit and missing recorded IDs, omitted cwd, explicit relative
cwd, older transcripts, the exact since boundary, missing Codex cwd metadata,
invalid timestamps, exact ID isolation, pagination and all structured providers.

Verification results (all measured by the runner):

- `npm run lint`: passed, including documentation validation, Ruff, Node syntax
  checks and Python compilation. There is no separate typecheck script.
- Full suite with cleared environment: 1812 passed, 5 skipped (opt-in
  acceptance), 3 existing Python deprecation warnings. A final `npm test` retry
  after the exact-ID test assertion reported 1811 passed, 5 skipped and one
  unrelated timing failure: `test/test_remote_antigravity_py.py::test_concurrent_fake_agy_attempt_is_refused`
  did not see its fake worker home file within its two-second startup deadline.
  The mission does not change this concurrency path or relax its assertions.
- `python -m pytest test/test_remote_antigravity_py.py`: all 20 passed on retry,
  including the concurrency test. The last full-suite failure is retained in the
  receipt and delivery report rather than hidden by the targeted retry.
- `python -m pytest test/test_commands_conversation_py.py`: 38 passed after
  adding an exact-ID assertion with an unrelated cwd and a future since cutoff.
- `PATH="$PWD/.venv/bin:$PATH" python -m pytest test/test_commands_conversation_py.py test/test_conversation_py.py test/test_interactive_usage_py.py`:
  343 passed, 1 skipped.
- `PATH="$HOME/.cargo/bin:$PATH" cargo test --manifest-path tray/Cargo.toml`:
  99 passed, two existing dead-code warnings.
- `npm pack --dry-run`: passed.
- `uv build --out-dir .jarvis-artifacts/dist`: source distribution and wheel built.
- `logics-manager lint --require-status`: passed.
- `logics-manager audit --group-by-doc`: passed with six existing warnings in
  unrelated agent-state and detached-failover documents.
- `git diff --check`: passed.

The final lint, CLI regression and full-suite retries use the development virtual
environment on PATH outside the runner, preserving the declared command strings.
The full-suite subprocess additionally clears the four inherited overrides named
above; this does not modify Git configuration or mission repository permissions.

Human review should check the additive scope contract, modification-time cutoff
semantics and the hub caller's use of panel cwd and session-start time. No real
host measurement is needed to accept this code change. Cross-platform CI remains
the merge gate.
