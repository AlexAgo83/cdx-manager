# Interactive history discovery — mission 00524d029e

## Scope and assumptions

The supplied Tower measurement reported 475 mission rows among the latest 500 launches, only 25 interactive sessions, 11 unverified remote-ops transcript matches, and a missing live Claude session. These are operator-supplied observations; this Spire checkout cannot independently measure Tower.

This is a bounded CLI/history correction. The identity rule is documented where it is enforced and covered by regression tests: exact provider IDs are evidence; recency alone never verifies a resume target. No shared operational or HQ design rule changes, and no edits to shared runbooks are required.

`--interactive` excludes all headless `action: run` rows, detached rows and mission-labelled rows. Unlabelled legacy launches remain eligible because their purpose cannot safely be inferred from their directory alone. `--cwd` matches the resolved directory exactly, including symlinks and user-home expansion; it does not include descendants.

## Changes

- Apply history filters before the limit and preserve the JSON envelope and summary/period behavior.
- Persist interactive history when the provider starts; atomically update that run's row at completion or failure. A terminal-capture retry retains the same runtime ID.
- Route `cdx start <profile>` through the existing interactive launch path. Include active older runtimes that have no persisted history row, without reconstructing vanished sessions.
- Resolve Claude IDs from the launch identity or legacy provider arguments. Resolve new Codex IDs only from a unique native session metadata record within the launch project/time window; use exact transcript lookup afterward. Do not replace the interactive Codex identity with a recency guess.
- Expose a bounded, redacted `first_user_prompt`, skipping provider wrappers, reminders, tools and bare paths. Preserve an explicit initial prompt if the native transcript is unavailable. Read-time enrichment leaves historical records untouched.
- Update README, CLI reference/help, session documentation and unreleased release notes.

## Local validation

All test and validation attempts are timed by `.jarvis-input/mission-test-runner.py`; the authoritative receipts are in `.jarvis-artifacts/mission-tests.jsonl`.

The initial environment selected system Python without Ruff. Installed locked development dependencies with `uv sync --frozen --extra dev` and selected the prepared virtual environment for subsequent checks. Initial suite attempts also inherited `GIT_DIR`, `GIT_COMMON_DIR`, `GIT_WORK_TREE` and `RTK_DB_PATH` from the execution sandbox. Remove these variables only for the test subprocess so temporary fixture repositories and RTK fixtures remain independent. The mission repository's Git metadata remains read-only.

Cargo was initially missing. Installed the public minimal Rust toolchain outside the repository; all 99 tray tests subsequently passed. npm packaging dry-run and wheel build passed. No standalone typecheck script exists; lint includes Python compilation and Ruff.

Successful validation commands (all executed through the mission timer):

```sh
PATH="$PWD/.venv/bin:$PATH" npm run lint
env -u GIT_COMMON_DIR -u GIT_DIR -u GIT_WORK_TREE -u RTK_DB_PATH PATH="$PWD/.venv/bin:$PATH" npm test
PATH="/home/agent/.cargo/bin:$PATH" cargo test --manifest-path tray/Cargo.toml
PATH="$PWD/.venv/bin:$PATH" npm pack --dry-run
PATH="$PWD/.venv/bin:$PATH" python -m build --wheel --outdir .jarvis-artifacts/wheels
logics-manager lint --require-status
logics-manager audit --group-by-doc --paths logics/runbook/fragments/2026-11-04-interactive-history-00524d029e.md
git diff --check
```

Final Python suite: 1,848 passed, 5 skipped, with 3 existing deprecation warnings. Rust suite: 99 passed. Final lint, packaging, wheel build and Logics checks passed. Earlier failed attempts and their retries remain in the timer receipts.

The regression tests cover filtering before limit, resolved directory matching, live tmux launch discovery, completion/failure deduplication, active legacy runtimes, exact identities despite unrelated transcripts, ambiguous Codex metadata, missing transcripts, prompt cleanup, bounded reads and prompt text that resembles provider arguments.

## Tower measurement still required

Host: Tower. User: aagos. Run this read-only probe after the guarded deployment:

```sh
cdx history grif --cwd /home/aagos/projects/AlexAgo83/remote-ops --interactive --limit 500 --json
```

Acceptance: the still-live `jarvis-remote-ops` Claude launch appears with its correct conversation ID and exact transcript match; its first user prompt contains real user text; mission/detached rows do not consume the filtered window. A session whose native transcript cannot be verified must remain explicitly unverified. Local fixtures do not establish this host measurement.
