# Mission e700ca413f: Claude quota status line

## Delivery decisions

- Read the owning Claude profile's `lastStatus` from the existing `sessions.json`,
  without a provider call, authentication refresh, CLI import or store lock during
  rendering. Pin the store in the installed command and resolve identity from the
  provider HOME, falling back to CDX_SESSION_NAME only when HOME is absent.
- Reuse the current launcher menu's eight-cell block gauge through a shared glyph
  strip. The mission's heavy/light line example predates the current block glyphs;
  preserve the current launcher appearance rather than restoring the old glyphs.
- Show both windows, the profile name, cached reset times below 20%, and `stale`
  for readings outside the existing ten-minute Claude cache lifetime. Respect
  per-window evidence timestamps when a merged status contains older quota.
- Install on creation, copy, rename, import, settings changes and interactive
  launch/resume. Preserve operator statusLine values, report conflicts, and remove
  only the cdx-owned command with `cdx set PROFILE --status-line off`.
- Leave Codex configuration untouched. Its documented `tui.status_line` configures
  built-in footer item identifiers, not a Claude-style shell command.
  Source: https://learn.chatgpt.com/docs/config-file/config-reference

## Verification environment

All local check attempts run through `.jarvis-input/mission-test-runner.py`.
Measured receipts are in `.jarvis-artifacts/mission-tests.jsonl`.
The initial `npm test` inherited GIT_DIR, GIT_COMMON_DIR, GIT_WORK_TREE and
RTK_DB_PATH from the mission environment. Six tests failed in temporary Git
fixtures or RTK path expectations. Removing only GIT_DIR/GIT_WORK_TREE and
RTK_DB_PATH fixed RTK but left four Git fixture failures; GIT_COMMON_DIR also
needs removal for independent temporary test repositories. The mission repository
itself remains read-only to Git. No production Git or RTK behavior was changed.
The first lint attempt used system Python without ruff. Install the lockfile's
existing dev extra using `uv sync --frozen --extra dev` and put `.venv/bin` first
in PATH for the final lint run.

## Human review

Review one real interactive Claude session's footer, particularly terminal-width
wrapping and the operator-defined statusLine conflict notice. Browser screenshots
are previews of actual renderer output, not authenticated Claude sessions.
Full green GitHub CI on the merged commit remains mandatory before merge.

## Final local results

The full suite passed with 1,898 tests and five skips, including 33 new footer
tests. The tray suite passed all 99 tests. The final Python suite and lint use the
lockfile dev environment. A previous clean-environment suite printed a passing
summary but its measurement process exited 143 before writing a final receipt;
the repeated full command below has a completed zero-exit receipt. Cargo was
initially missing; a temporary minimal Rust toolchain installed from the public
rustup distribution enabled the required tray check. It is removed from retained
artifacts after verification.

The following durations come directly from the completed timer receipts and
include shared-lock waiting where applicable.

| Exact command | Exit | Measured seconds |
| --- | --- | --- |
| `env -u GIT_DIR -u GIT_COMMON_DIR -u GIT_WORK_TREE -u RTK_DB_PATH npm test` | 0 | 66.739 |
| `npm run lint` | 0 | 330.527 |
| `cargo test --locked --manifest-path tray/Cargo.toml` | 0 | 29.88 |
| `npm pack --dry-run` | 0 | 30.363 |
| `uv build --wheel --out-dir .jarvis-artifacts/wheels` | 0 | 280.45 |
| `python3 .jarvis-artifacts/check-status-line-wheel.py` | 0 | 40.054 |
| `python3 .jarvis-artifacts/status-line-benchmark.py` | 0 | 330.468 |
| `node .jarvis-artifacts/status-line-preview.cjs` | 0 | 280.744 |
| `logics-manager lint` | 0 | 230.285 |
| `git diff --check` | 0 | 190.069 |

The 30-render benchmark measured 13.90 ms median, 15.17 ms p95 and 16.54 ms
maximum, including interpreter startup. The wheel smoke test executes the packaged
standalone script and its shared gauge data after extraction. The project has no
separate typecheck command; lint includes Python compilation.

Preview PNG artifacts inspected in both themes and widths:

- `.jarvis-artifacts/status-line-375-light.png`
- `.jarvis-artifacts/status-line-375-dark.png`
- `.jarvis-artifacts/status-line-1280-light.png`
- `.jarvis-artifacts/status-line-1280-dark.png`
