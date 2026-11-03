# Allowlist conversation records — mission e8112bdb98

## Scope and assumptions

The reported incident concerns Claude Code 2.1.317, profile `grif`, and a
2026-11-04 transcript named `1fb12a46-….jsonl`. That private transcript is not
present in the supplied checkout or mission inputs. The new fixture is a minimal
reconstruction of the supplied `api-request-blob` record shape, with neutral
message text and synthetic identifiers; it is not represented as a captured real
transcript. A reviewer with access should compare it against a sanitized real
excerpt before release.

The normal reader already required `message`, but did not constrain the outer
Claude record type. Apply a positive allowlist before interpreting content:
Claude and Antigravity accept only `user` and `assistant` with a message object;
Codex accepts only `response_item` with a payload object. Tool calls and results
inside those records retain their existing summaries and name association.

Oversized records use the same allowlist. If the bounded prefix cannot establish
the outer type and message object, discard the record without a placeholder.
This deliberately prefers omission over inventing conversation entries from
provider bookkeeping. New tests update the oversized fixtures to include real
outer conversation types, and cover ignored oversized events and later cursor
progress. Existing bounded reads, incomplete-tail retry and stable IDs remain.

This is a local parser correction whose reasoning is recorded in the allowlist
comment and regression tests (ADR 030); no separate workflow chain or changes to
shared operating/design rules are needed. Version declarations and the new
versioned changelog target 0.26.2. Publication and release evidence remain the
supervisor's responsibility; no commits, pushes or PR creation were attempted.

## Validation

Every local check runs through `.jarvis-input/mission-test-runner.py`; exact
commands, elapsed times and exit codes are in
`.jarvis-artifacts/mission-tests.jsonl`.

The initial `npm run lint` lacked Ruff, and the initial `npm test` inherited Git
path variables and `RTK_DB_PATH` that interfered with synthetic test repositories
and history fixtures. It also hit the existing remote Antigravity timeout test
before its fake worker had created the receipt file. Install frozen development
dependencies with `uv sync --frozen --extra dev`, add `.venv/bin` to PATH, and
unset `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`, and `RTK_DB_PATH` for test
processes. This does not change the mission checkout's Git permissions. Install
public Rust tooling and add its Cargo directory to PATH for tray validation.

Checks include full `npm test`, `npm run lint`, targeted conversation tests,
`cargo test --manifest-path tray/Cargo.toml`,
`uv build --wheel --out-dir .jarvis-artifacts/wheels`, `npm pack --dry-run`,
`npm run release:validate`, `uv lock --check`, Logics lint/audit and
`git diff --check`. No separate typecheck script exists; lint includes Python
compilation. No UI changes or host measurements are required.

Targeted coverage verifies dated user messages occur once, request blobs add no
undated entries, tool results retain their names, pagination matches a complete
read, and unknown record types are ignored for every structured provider even
when they carry plausible messages. The fixture is reconstructed; real-incident
comparison remains the human review limitation described above.

Final results: full suite 1,629 passed and 5 skipped; the final targeted run
138 passed and 1 skipped; tray suite 99 passed. Lint, wheel build, npm package
dry-run, release metadata validation, lock consistency, Logics lint/audit and
whitespace validation passed. The audit reports six pre-existing warnings in
unchanged agent-state/failover documents. The skips are the Codex case of the
Claude-format fixture and four existing optional workspace-sandbox checks.
