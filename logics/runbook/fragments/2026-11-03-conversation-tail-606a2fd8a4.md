# Conversation tail pagination — mission 606a2fd8a4

## Scope and conservative assumptions

This checkout is cdx-manager, rather than the remote-ops hub repository suggested
by the scheduling paths. Implement the requested provider-reader and CLI contract
here; no hub UI or shared operating/design rule changes are needed. Keep the
current release version unchanged and record this feature under Unreleased for
the planned 0.26.2 publication. No commit, push or PR creation is performed.

The reasoning lives beside the reverse reader, in the README contract and in
regression tests, so this local reader extension needs no separate Logics chain.
Use `--tail N` for the count, or `--before CURSOR --limit N` for previous pages.
Accept `--tail N --before CURSOR` too, with tail taking precedence over limit.
Reject combining a forward cursor with either new option.

## Implementation and limits

Read backwards in 64 KiB blocks and retain only the first 1 MiB plus one byte of
each record. Normalize selected records in forward order through the existing
redaction, role, tool-summary and oversized-placeholder implementation. Page
boundaries include content-block indexes, keeping file-position IDs unchanged.
Incomplete trailing records are retried by the forward cursor after completion.

Recover recent tool-call names from a 64 KiB lookback, extending to the existing
8 MiB scan budget when selected results need earlier calls. Finish a record even
when it crosses this budget. Keep the existing bounded cursor name cache and
conservative `tool` fallback. Finding N visible entries may scan further when
records have no entries or contain very large attachments; memory and individual
read sizes remain bounded independently of individual record length.

Backward cursors are distinct version-2 cursors. They bind file identity, byte
position, block index, original size, modification time and boundary anchors.
Detect replacement, truncation and same-size rewrites while allowing appends.
As documented for forward reading, files must remain append-only: bounded
boundary checks cannot prove that arbitrary earlier bytes were not edited while
the file also grew. No complete-file hash or index is introduced.

## Measured verification

Every local check attempt uses `.jarvis-input/mission-test-runner.py`. Its exact
commands, durations and exit codes are retained in
`.jarvis-artifacts/mission-tests.jsonl`; the targeted JUnit report is
`.jarvis-artifacts/conversation-tests.xml`.

For 6,000 normalized entries and `tail=25`, measured reads total 131,456 bytes:

- Codex transcript: 580,890 bytes total (22.6% read).
- Claude transcript: 556,890 bytes total (23.6% read).
- Antigravity transcript: 556,890 bytes total (23.6% read).

The instrumented reader rejects unbounded reads and forward `readline` calls
for this initial-tail measurement. The largest read is 65,536 bytes. All 6,000
entries are recovered by chaining backward pages, in chronological order and
without repeated IDs. Additional coverage includes content-block splits, tool
name recovery and subsequent results, append polling, malformed/empty records,
20 MiB placeholders, incomplete oversized tails, stale/replaced files, forged
block indexes, range validation and CLI option combinations.

Initial baseline attempts exposed missing Ruff/Cargo and inherited Git/RTK path
variables affecting unrelated tests. Install frozen development dependencies
with `uv sync --frozen --extra dev`, use `.venv/bin` on PATH, and unset `GIT_DIR`,
`GIT_WORK_TREE`, `GIT_COMMON_DIR` and `RTK_DB_PATH` for test subprocesses. Install
public Rust tooling and use its Cargo bin directory. These environment changes
do not mutate the mission checkout's read-only Git metadata.

Validation commands:

- `env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR -u RTK_DB_PATH PATH="$PWD/.venv/bin:$PATH" npm test`
- `env PATH="$PWD/.venv/bin:$PATH" npm run lint`
- `env PATH="$PWD/.venv/bin:$PATH" python -m pytest test/test_conversation_py.py test/test_commands_conversation_py.py -o junit_family=xunit1 --junitxml=.jarvis-artifacts/conversation-tests.xml`
- `env PATH="$HOME/.cargo/bin:$PATH" cargo test --manifest-path tray/Cargo.toml`
- `uv build --wheel --out-dir .jarvis-artifacts/wheels`
- `npm pack --dry-run`
- `logics-manager lint --require-status`
- `logics-manager audit --group-by-doc`
- `git diff --check`

Final results: 1,596 Python tests passed and 4 environment-dependent tests were
skipped; all 103 targeted tests and 99 Rust tests passed. Lint, wheel build, npm
package dry-run, Logics lint and whitespace validation passed. The Logics audit
returned zero blocking issues and six pre-existing warnings in unrelated agent
state and failover documents.

There is no separate typecheck script and no UI change requiring screenshots.
Human review should check the backward/live cursor integration expected by the
hub, the documented append-only assumption and bounded tool-name fallback. No
real provider transcript, operator credential or host measurement is required.
