# Mission 40d98be295: optional automatic mission concurrency

## Scope and assumptions

Store an optional integer `launch.max_parallel` from 0 to 5. Zero excludes a
profile from automatic missions; absence leaves the scheduling client's rule
in effect. Enforcement belongs to that client. The existing `cdx run
--max-parallel` contract remains separate.

This checkout has `cdx --json` and `cdx config`, but no `ls` or `show` commands.
Add `ls` as the list entry point and `show` as an alias of `config` to provide
the requested surfaces without duplicating their implementations.

This change needs no workflow chain: the validation declaration, README
contract, and command regression tests contain its rationale and evidence.

## Implementation

- Validate CLI and service inputs with a shared validator, including rejection
  of booleans and fractional service inputs.
- Preserve the field across unrelated setting changes and store reloads.
- Remove it through `unset --max-parallel` or `unset --all`.
- Expose it in list JSON under `launch`, status JSON as a nullable row field,
  and the per-profile settings display.
- Keep older configurations free of an implicit profile-specific ceiling.

## Validation environment

Every check is timed by `.jarvis-input/mission-test-runner.py`; receipts live in
`.jarvis-artifacts/mission-tests.jsonl` outside the published source changes.

The initial lint attempt lacked Ruff. Run `uv sync --extra dev --frozen`, then
use `uv run --no-sync` to select the prepared development environment.

The initial full suite inherited Spire's `GIT_DIR`, `GIT_WORK_TREE`,
`GIT_COMMON_DIR`, and `RTK_DB_PATH`. These affect temporary fixture repositories
and RTK history assertions. Unset them for the test subprocess only; never
change the mission repository's Git metadata. A retry that omitted
`GIT_COMMON_DIR` still failed temporary repository setup.

Cargo was initially absent. Install a minimal public Rust toolchain under
`/tmp/mission-40d98be295-cargo` and `/tmp/mission-40d98be295-rustup` without
changing the operator's shell configuration.

## Verification results

- `uv run --no-sync npm run lint`: passed, including Ruff, documentation
  checks, JavaScript syntax, and Python compilation. No separate typecheck
  script is defined by this project.
- `uv run --no-sync python -m pytest test/test_commands_settings_py.py`:
  24 passed, including the three new regression tests.
- Clean-environment retry of the five initially affected Python test files:
  281 passed.
- `cargo test --manifest-path tray/Cargo.toml`, with the temporary toolchain
  selected through `CARGO_HOME`, `RUSTUP_HOME`, and `PATH`: 99 passed.
- `npm pack --dry-run`: passed.
- `uv build --out-dir /tmp/mission-40d98be295-dist`: built the wheel and sdist.
- `logics-manager lint --require-status`: passed.
- `logics-manager audit --group-by-doc`: passed with six existing warnings.
- `git diff --check`: passed.

A full clean-environment run reached 1,489 passing tests and four skips, but
`test/test_remote_antigravity_py.py::test_remote_timeout_removes_attempt_home`
failed because its 0.5-second timeout expired before the fake worker wrote its
home marker. The entire Antigravity test file passed on an isolated retry
(20 tests). No unrelated timeout assertions were weakened. A final full suite
retry runs without concurrent checks.

Final full-suite retry: **1,490 passed, four skipped**, exit code 0.
Exact timed command:

```sh
env -u GIT_COMMON_DIR -u GIT_INDEX_FILE -u GIT_DIR -u GIT_WORK_TREE -u RTK_DB_PATH uv run --no-sync npm test
```

The timer receipt records 165.472 seconds for this attempt.

Human review should confirm that the scheduling client consumes zero as
exclusion and absence as its own default. No host measurement is needed for
this CLI metadata change. All source edits remain uncommitted for Jarvis.
