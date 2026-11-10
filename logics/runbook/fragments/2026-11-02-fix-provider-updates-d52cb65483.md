# Provider update detection and verification (mission d52cb65483)

## Decision and compatibility

Read both stdout and stderr for advertised native updaters. The shared parser
covers Claude, Antigravity, and RTK; Codex retains its existing explicit updater.
Version probes also combine both streams so an Ollama client warning on stderr
wins over a server version on stdout.

After a successful tool update command, probe the installed CLI again. Fail the
action if its version is unchanged, missing, downgraded, or still below the
published version. Keep the pre-update JSON plan and existing fields/statuses;
results add `version_before`, `version_after`, and `latest_version`. Verification
failure sets a nonzero `returncode` and explains the failure in `reason` and
`stderr`. Successful text output shows the version transition, including majors.

Ollama's vendor API can return HTTP 204 on Linux. Empty, invalid, or failed
responses now fall back to the latest stable GitHub release for `ollama/ollama`.
If GitHub also fails or returns unusable data, retain `unknown`. Tests use the
mission's measured versions: installed 0.32.5 and published v0.40.13.

No safe unattended Linux installation path is established. The vendor installer
writes system paths and can restart a service. Host A's `~/.local/bin/ollama`
location does not establish that the executable is unused by a running service.
Therefore every Linux Ollama update stays `update_available`, with
`update_command: null` and an explicit manual-maintenance reason. Do not replace
the binary, run an installer, restart a service, or interrupt models. An operator
must arrange an appropriate maintenance window before updating Ollama manually.

## Evidence and validation

The fixture `test/fixtures/agy-help.txt` is the complete actual stderr from
`/home/user/.local/bin/agy --help` on Host B during this mission. It contains
40 lines and stdout was empty (the supplied earlier measurement had 34 lines).
It retains `Available subcommands:` and the indented `update` / `Update CLI`
entry. No host updater was executed. Tests exercise this fixture on both streams,
missing subcommands, a 1.1.11 to 2.0.0 transition, unchanged/missing/partial
versions, CLI JSON failure propagation, Linux HTTP 204 fallback, GitHub failure,
and the absence of any Linux Ollama installation action.

All local validation attempts run through `.mission-input/mission-test-runner.py`;
exact timings and exit codes remain in `.mission-artifacts/mission-tests.jsonl`.
Initial lint lacked ruff; `uv sync --frozen --extra dev` restored locked dev
packages. Subsequent failures exposed test-fixture argument binding and stale
expectations about the additional version probe; these were corrected. Cargo
was initially absent; a minimal public Rust toolchain was installed under
`/tmp/d52cb65483-{cargo,rustup}` and the unchanged command was retried.

Validation commands:

- `npm run lint` (includes Python compilation; no separate typecheck exists).
- `npm test` (full Python suite).
- `python3 -m pytest test/test_update_all_py.py test/test_commands_maintenance_py.py`.
- `cargo test --manifest-path tray/Cargo.toml` (99 tests).
- `npm pack --dry-run`.
- `uv build --wheel --out-dir /tmp/cdx-mission-d52cb65483-dist`.

No UI changed, no release was published, and no commit, push, or PR was made.
Tests simulate update execution; they do not certify a real host upgrade.
Human review should assess example-project compatibility with the additive result
fields and the deliberate manual Linux Ollama policy.

Final results: lint passed; the full Python suite passed 1,414 tests (three
existing asyncio deprecation warnings); the targeted suite passed 67 tests;
all 99 Rust tests passed; npm package dry-run and wheel build passed. Earlier
failed attempts and successful retries remain in the timer receipt.
