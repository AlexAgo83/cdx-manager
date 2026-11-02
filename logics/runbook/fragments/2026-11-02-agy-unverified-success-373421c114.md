# Antigravity update verification (mission 373421c114)

## Change and conservative assumption

This checkout is cdx-manager. A zero-exit `agy update` is a successful native
updater invocation, but cannot certify currency when no expected newer CLI
version is known. Keep the inventory `unknown` and `latest_version: null`;
never infer a release from the editor feed or invent a CLI version source.
An unverified success now carries `update_unverified` in its result and the
JSON envelope warnings, with the same warning rendered in text. Explicit
already-current output and observed version advancement still succeed without
that warning. Non-zero updater exits retain their original failure code/output.
Known expected upgrades and other providers retain their verification rules.

Faked updater tests cover already current, version advanced, successful but
unverifiable (including missing version output), and non-zero failure, with
CLI exit codes, failed counts, unknown status, JSON warnings and text rendering.
The CLI schema publishes the warning code. Unreleased notes describe the change.

## Validation environment and attempts

All test/check commands use `.jarvis-input/mission-test-runner.py`, with exact
commands, exit codes and measured durations in
`.jarvis-artifacts/mission-tests.jsonl`. No receipt is edited.

The initial `npm test` run had four failures and two fixture errors because the
sandbox exports repository-specific Git variables and `RTK_DB_PATH`. The retry
unsets only `GIT_DIR`, `GIT_COMMON_DIR`, `GIT_WORK_TREE`, and `RTK_DB_PATH` in the
test subprocess so temporary Git repositories and faked RTK histories remain
independent. The mission repository Git metadata remains read-only. A subsequent
full run detected the missing warning schema entry; that entry was added.
Initial `npm run lint` lacked ruff; `uv sync --frozen --extra dev` restored the
locked development tools. Cargo was absent; a public minimal Rust toolchain was
installed under mission-specific `/tmp` paths. The first prefixed Cargo retry
failed from an unquoted PATH containing spaces; the corrected command quotes it.

## Final checks

- `uv run --no-sync npm run lint`: passed (documentation checks, JavaScript
  syntax, Ruff, Python compilation). No separate typecheck script exists.
- `uv run --no-sync python -m pytest test/test_update_all_py.py test/test_commands_maintenance_py.py`:
  passed, 72 tests before the final expanded CLI outcome matrix.
- `env -u GIT_DIR -u GIT_COMMON_DIR -u GIT_WORK_TREE -u RTK_DB_PATH uv run --no-sync npm test`:
  passed, 1,425 tests and four skips (39.395 seconds measured by the runner).
- `CARGO_HOME=/tmp/373421c114-cargo RUSTUP_HOME=/tmp/373421c114-rustup PATH="/tmp/373421c114-cargo/bin:$PATH" cargo test --manifest-path tray/Cargo.toml`:
  passed, 99 tests, existing dead-code warnings.
- `logics-manager lint --require-status`: passed.
- `npm pack --dry-run`: passed.
- `uv build --wheel --out-dir /tmp/cdx-mission-373421c114-dist`: passed.

No real workstation updater was invoked, no provider binary or service was
modified, and no host recovery is claimed from fixtures. Human review should
check the uncertainty semantics and CI matrix. No graphical UI change requires
screenshots. Changes remain in the working tree for supervisor publication;
no commit, push or PR was performed by this mission.
