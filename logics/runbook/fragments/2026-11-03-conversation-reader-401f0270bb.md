# Incremental conversation reader — mission 401f0270bb

## Delivery and conservative assumptions

Add `cdx conversation <name> --json` and the reusable
`cdx_manager.conversation.read_conversation` function. Reuse exact conversation
resolution and the existing recency fallback only when no conversation ID is
known. Codex uses canonical response items; Claude and Antigravity use the
Claude-compatible JSONL layout already understood by the transcript resolver.
Ollama terminal captures have no reliable role boundaries and explicitly return
`unsupported`, even if a terminal capture is available. Missing structured
transcripts return `unavailable`.

The contract lives beside its reader, in README documentation and fixture tests;
no existing workflow status, operating rule or shared design document changes.
No provider login, live inference, deployment, mission repository Git mutation or publication is
part of this mission.

## Pagination and privacy

Versioned opaque cursors retain file identity, byte offset, content-block index,
a small preceding-byte digest and up to 100 tool-name mappings. Resume seeks
rather than replaying the transcript. Partial trailing lines wait for a newline.
Rotation, truncation or an invalid cursor requires a client reset. Providers must
append records; arbitrary edits far before the cursor are outside this contract.
Reads scan at most 8 MiB and reject individual records above 1 MiB.

Tool arguments, results, attachments, metadata and reasoning are omitted. Tool
summaries state call/result presence without reproducing bodies. Known credential
patterns and labelled assignments in message text are redacted. No reusable text
redactor existed; the existing argv redactor only replaces prompt arguments.
Arbitrary unlabelled sensitive prose cannot be detected reliably.

## Validation

All local check attempts use `.jarvis-input/mission-test-runner.py`; authoritative
durations and exit codes are in `.jarvis-artifacts/mission-tests.jsonl`.
The initial environment lacked Ruff and Cargo, and inherited Git overrides and
RTK history settings contaminated baseline tests. Development Python dependencies
were installed from the frozen lockfile, and public Rust tooling was installed.
Test processes clear inherited Git overrides and RTK_DB_PATH so temporary test
repositories and fake RTK fixtures are isolated. Repository Git stays read-only.

Human review should assess provider format assumptions and the documented privacy
limits. Real provider sessions were not opened and no production measurement is
required by this local read-only feature.

Verified commands (through the supplied timer):

- `npm run lint`: passed with the prepared virtual environment on PATH.
- `npm test`: passed after clearing inherited Git and RTK environment overrides;
  final full run: 1526 passed and 4 skipped, including the built-in-tool regression.
- Targeted reader and CLI suite: 39 passed, including the final regression.
- `cargo test --manifest-path tray/Cargo.toml`: 99 passed after installing Rust.
- `npm pack --dry-run`: passed.
- `uv build --wheel --out-dir .jarvis-artifacts/wheels`: passed.
- `logics-manager lint --require-status`: passed.
- `logics-manager audit --group-by-doc`: passed, with six existing warnings in
  unrelated agent-state/failover workflow documents.

There is no separate typecheck script. No UI changes or screenshots are needed.
