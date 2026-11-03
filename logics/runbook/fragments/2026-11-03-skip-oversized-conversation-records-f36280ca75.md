# Skip oversized conversation records — mission f36280ca75

## Scope and conservative assumptions

The supplied incident describes a Claude transcript whose oversized image record
prevents access to newer messages. This is a local reader fix: its reasoning lives
in the bounded-read comment, README contract and regression tests, so no separate
Logics request chain or shared operating/design rule changes are needed.

Read at most 1 MiB plus one byte per chunk. For an oversized record, retain only
the initial bounded prefix long enough to recover structural role metadata, then
discard chunks until the newline. Emit one short placeholder using the existing
file-position ID scheme. Metadata after an incomplete JSON value is unavailable;
use `tool` when a role cannot be safely determined. Never infer roles from text,
image data or attachment contents.

The 8 MiB page scan budget is checked between records. Completing one oversized
record can exceed it; subsequent records are read on the next page. This avoids
adding skip state to the cursor. An incomplete trailing record leaves the cursor
at its original start and emits nothing until a newline arrives, even if repeated
polls must rescan it. Memory remains bounded independently of record length.

Keep the version-1 cursor schema and accept its existing 100-name cache. Before
emitting a cursor, evict oldest mappings until their compact JSON fits in 2 KiB.
Evicted results use the existing `tool` fallback. Both old and new readers can
consume the smaller cursors; no compression format or runtime dependency is added.

## Validation and review

Every local check attempt is timed by `.jarvis-input/mission-test-runner.py`.
Exact commands, durations and exit codes are in
`.jarvis-artifacts/mission-tests.jsonl`. Initial checks exposed missing Ruff in the
system interpreter and inherited Git/RTK environment settings affecting temporary
test repositories and fake history data. Install frozen development dependencies
with `uv sync --frozen --extra dev`, put `.venv/bin` on PATH, and unset `GIT_DIR`,
`GIT_WORK_TREE`, `GIT_COMMON_DIR` and `RTK_DB_PATH` for the suite process. These
changes do not alter the mission repository's read-only Git metadata. Public Rust
tooling was installed to run the required tray checks.

Regression coverage includes all three structured providers, a 20 MiB middle
record, cursor resumption immediately before it, bounded read sizes, later entries,
stable IDs, repeated polls of an incomplete oversized tail, conservative role
recovery and acceptance/trimming of a legacy cursor with 100 long tool names.

Final checks (all through the supplied timer):

- `npm test`: 1,559 passed, 4 skipped; the final retry passed after clearing all
  three inherited Git path variables and the RTK database override.
- `env PATH="$PWD/.venv/bin:$PATH" python -m pytest test/test_conversation_py.py test/test_commands_conversation_py.py`:
  66 passed.
- `npm run lint`: passed with `.venv/bin` on PATH.
- `cargo test --manifest-path tray/Cargo.toml`: 99 passed with the installed Cargo
  directory on PATH.
- `uv build --wheel --out-dir .jarvis-artifacts/wheels`: passed.
- `npm pack --dry-run`: passed.
- `logics-manager lint --require-status`: passed.
- `logics-manager audit --group-by-doc`: passed with six pre-existing warnings in
  unrelated agent-state and failover workflow documents.
- `git diff --check`: passed.

There is no separate typecheck script and no UI change. Human review should check
role recovery against real provider field ordering and assess the documented scan
budget exception and tool-name eviction tradeoff. No real transcript or provider
session was accessed; production or host measurements are not required.
