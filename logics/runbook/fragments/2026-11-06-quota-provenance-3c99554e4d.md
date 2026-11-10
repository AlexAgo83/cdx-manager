# Mission 3c99554e4d: quota provenance and profile freshness

The additive `quota_windows` status contract uses the existing Codex
`account/rateLimits/read` reader and Claude one-token probe. No second probe,
new endpoint, credential lookup mechanism, or deployment operation is added.

Conservative assumptions: the existing cache TTLs define staleness (Codex
300 seconds, Claude 600 seconds). Legacy/local evidence without a known
provider origin is `cache`; missing windows are `unknown`. Claude statusline
is a reserved, explicitly identified source, not a new collection mechanism.
Read failures describe the current command and preserve cached measurements.

The implementation and regression tests carry the reasoning at the affected
status declarations; no new lifecycle chain or shared operating rule is needed.
Validation results are recorded by the supplied mission test runner in
`.mission-artifacts/mission-tests.jsonl`. Publication still requires green
required GitHub CI on the merged commit. No live authenticated provider
measurement is claimed from synthetic tests.

Validation: `npm test` passed with 1,865 tests and five existing skips;
`cargo test --manifest-path tray/Cargo.toml` passed all 99 tests. Lint,
`npm pack --dry-run`, and the wheel build passed. Logics lint passed; the
full audit reported zero blockers and six existing warnings.

The sandbox exports `GIT_DIR`, `GIT_COMMON_DIR`, `GIT_WORK_TREE`, and
`RTK_DB_PATH`. Initial full-suite attempts exposed these variables leaking
into temporary Git fixtures and mocked RTK histories. The successful full
suite used `env -u RTK_DB_PATH -u GIT_DIR -u GIT_COMMON_DIR -u GIT_WORK_TREE
-u GIT_INDEX_FILE python3 .mission-input/mission-test-runner.py 'npm test'`.
This confines fixture Git mutations to their temporary repositories; the
mission repository stays read-only. An intermediate queued retry was
cancelled before execution after discovering the remaining Git override.
New CLI tests disable update checks so their HTTP call counts measure only
the existing quota probe.

The targeted quota suite passed all 13 cases. Two earlier queued validation
attempts exhausted the shared test-lock timeout before executing; both were
retried through the unchanged supplied runner. Receipts retain every attempt.
