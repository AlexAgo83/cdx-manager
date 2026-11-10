# Antigravity CLI version uncertainty (mission b49b1edf53)

## Decision and scope

Stop using the editor `/releases` endpoint for `agy`: the mission's supplied
2026-11-02 measurement reports feed versions 2.0.0, 1.23.2 and 1.22.2 while
CLI 1.4.12 reports `You are already on the latest version.`. These version
series cannot establish that the CLI is outdated.

Keep `latest_version: null` and `status: unknown`. Schedule the known native
`agy update` command for confirmed application, including `--yes`; inventory
collection only reads the installed version. Other tools retain their existing
sources and update selection. The shared post-update verification accepts a
zero-exit updater's explicit current-version message on either stream when the
installed version is unchanged. Otherwise require a version increase reaching
the published release when known, and preserve nonzero updater exits.

The decision is recorded beside the agy declaration, in regression tests, and
in this mission fragment, as requested; no separate workflow chain is created.
No shared runbook or the orchestrator design history was changed.

## Read-only evidence

`agy` was initially outside PATH. Absolute probes on Host B succeeded:

- `/home/user/.local/bin/agy --version`: exit 0, output `1.4.12`.
- `/home/user/.local/bin/agy update --help`: exit 2, output
  `Usage of update:`; no read-only check option is documented.

The conservative assumption is that no reliable read-only latest-CLI source
is established. No update/check flags were guessed and no real updater was run.
`test/fixtures/agy-update-already-latest.txt` preserves the exact output line
supplied by the mission, not a newly measured updater run.

## Validation

Every test/check/build attempt used `.mission-input/mission-test-runner.py`;
its unmodified receipt is `.mission-artifacts/mission-tests.jsonl`.

Final results:

- `npm run lint`: passed (includes documentation checks and Python compilation;
  no separate typecheck script exists).
- `npm test`: 1,419 passed, with three existing asyncio deprecation warnings.
- `python3 -m pytest test/test_update_all_py.py test/test_commands_maintenance_py.py`:
  72 passed. Covers the supplied output on stdout/stderr, shared verification,
  increased versions, unchanged/missing/downgraded versions without confirmation,
  incomplete upgrades against a known release, updater failure, no feed fetch,
  read-only inventory, and unknown JSON/text status after `--yes` success.
- `cargo test --manifest-path tray/Cargo.toml`: 99 passed, with two existing
  dead-code warnings.
- `npm pack --dry-run`: passed.
- `uv build --wheel --out-dir /tmp/cdx-mission-b49b1edf53-dist`: passed.

Initial lint failed because the selected Python lacked ruff; locked dev extras
were installed with `uv sync --frozen --extra dev`, and checks used `.venv/bin`
on PATH. A subsequent lint caught an unbound test closure variable, which was
fixed before successful validation. Cargo initially was absent; a public minimal
Rust toolchain under `/tmp/b49b1edf53-{cargo,rustup}` enabled the unchanged test
command to pass. All attempts and retries remain in the timer receipt.

No graphical UI changed. No release, commit, push, or PR was created. Human
review should check the deliberate distinction between a successful updater
and an unknown latest-version inventory, and the narrowly matched confirmation
line. No host measurement remains required for this code change; tests do not
claim that a real update was performed.
