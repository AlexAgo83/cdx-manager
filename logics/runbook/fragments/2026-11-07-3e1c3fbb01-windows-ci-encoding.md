# Mission 3e1c3fbb01: Repair Windows CI encoding failures

## Scope and evidence

Repair PR #119 on its existing mission branch without committing, pushing or
changing CI gates. The supplied GitHub and Host A context files were read as
bounded evidence. The supplied Windows log reports one standalone status-line
failure and three contract-test decoding failures. No Windows execution is
available locally; green required GitHub CI remains mandatory before merge.

This is a local correctness fix under ADR 030: its rationale lives beside the
UTF-8 output declaration and in the executable regression test, without a new
workflow chain. No shared operating or design rule changes.

## Changes

- Configure stdout as UTF-8 at the standalone status-line entry point. A pipe on
  Windows otherwise inherits an ANSI code page that cannot encode the gauge.
- Exercise the installed shell command with a store path containing spaces and
  inherited UTF-8, CP1252 and ASCII output encodings. Decode as UTF-8 and assert
  the entire rendered line, including the gauge.
- Read source, metadata and documentation fixtures explicitly as UTF-8 in the
  CLI and session-service contract tests instead of using the Windows locale.
- Record the encoding fix in the unreleased changelog.

## Validation

Every local check runs through `.mission-input/mission-test-runner.py`; measured
receipts live in `.mission-artifacts/mission-tests.jsonl`. Shared-lock waits are
included in the receipts. The CP1252 and ASCII regression cases failed before
the production fix, confirming that a non-UTF-8 pipe could crash the command.

The first full test attempt also inherited GIT_DIR, GIT_COMMON_DIR, GIT_WORK_TREE
and RTK_DB_PATH from Host B. These interfere with temporary Git fixtures and
operator-history expectations. Final test processes unset only those variables.
The prepared dependency environment lacked the dev extra and Rust: installed
the existing locked dev dependencies with `uv sync --frozen --extra dev` and
the public minimal Rust toolchain. Final checks put `.venv/bin` and the Rust
toolchain on PATH. No dependency or lockfile changes are needed.

Shared-lock contention caused one Rust attempt and one full Python attempt to
time out before execution; both passed on retry with their exact commands. The
initial lint attempt used system Python without ruff; the final attempt uses
the prepared virtual environment. These failed attempts remain in the receipts.
The final documentation recheck also encountered lock contention. Its retry
uses a timed outer invocation of the unchanged timed command, relying on the
runner's native inherited-lock support to allow a full lock-wait budget without
editing the runner, receipts or checks.

Final checks:

| Exact command | Result |
| --- | --- |
| `.venv/bin/python -m pytest test/test_claude_status_line_py.py test/test_cli_contract_py.py test/test_session_service_py.py -q` | Passed: 155 tests and 16 subtests, including all three pipe encodings. |
| `npm test` | Declared mission suite passed: 1,900 tests, 5 skipped, 3 warnings. |
| `npm run lint` | Passed: JavaScript syntax, project docs, ruff and Python compilation. |
| `cargo test --locked --manifest-path tray/Cargo.toml` | Passed: 99 tests. |
| `npm pack --dry-run && uv build --wheel --out-dir .mission-artifacts/wheels` | Passed: npm package dry-run and wheel build. |
| `logics-manager lint --require-status && logics-manager audit --group-by-doc && git diff --check` | Passed: zero blocking issues; six existing workflow audit warnings outside this fix. |

No separate typecheck script is configured. No UI layout or appearance changes
are made; no new visual captures are required. Before merge, the reviewer must
require green GitHub CI, including the real Windows matrix and required tests
on the merged commit. The supervisor must run its trusted secret scan before
publication. The sandbox does not run it. No commit, push or PR creation was
performed.
