# Antigravity quota capture (mission ac08160c4b)

The mission supplies measured agy 1.1.11 evidence from 2026-11-03: interactive
statusLine commands receive native quota on stdin, while headless JSON reports
run token counters. No signed-in account is available in this checkout; tests
use synthetic payloads only. No Google endpoint or OAuth token file is read.

The collector is installed in each new Antigravity profile and refreshed on
interactive launch, under the profile HOME at
`.gemini/antigravity-cli/settings.json`. Invalid settings and unsupported
statusLine types are preserved without modification. Existing command output
and its stdin are retained. The collector persists only time, plan_tier and
allowlisted quota fields in `.gemini/antigravity-cli/cdx-quota.json` with mode
0600 and atomic replacement. Missing quota replaces the previous reading with
unknown availability rather than reusing old percentages.

Status reads this local file even when the session registry contains cached
status. Gemini buckets populate 5H and WEEK; every other bucket remains in JSON.
Readings older than 24 hours are stale; a missing or elapsed reset makes that
bucket unknown. JSON includes reading_age_seconds, quota_status, quota_stale,
plan_tier and quota. The existing UPDATED column shows reading age and the
session detail shows the plan. No browser interface changes are involved.

Conservative accounting assumption: the supplied evidence does not establish
whether Antigravity input includes cache reads or output includes thinking.
Keep each measured counter and the native total, including through registry
normalization; do not infer token usage from quota changes. Interactive token
usage remains unavailable. A reviewer with a signed-in account can check that
an interactive launch refreshes quota while preserving their prior status line,
and that headless usage matches native agy JSON. No host deployment measurement
is required for this code change.

Validation commands and final results are recorded in the mission report and
in the supplied test runner receipts. The initial Python baseline inherited
Git and RTK environment overrides; subsequent full-suite runs remove those
variables only in the test subprocess, so fixture repositories use their own
metadata. Development tools come from the frozen dev extra.

## Final validation

Every test/check command below was executed through
`python3 .mission-input/mission-test-runner.py` as one unchanged quoted argument.
The authoritative timing receipts are in `.mission-artifacts/mission-tests.jsonl`.

- `PATH="$PWD/.venv/bin:$PATH" python -m pytest test/test_antigravity_usage_py.py -q`: 17 passed.
- `env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR -u GIT_CONFIG_COUNT -u GIT_CONFIG_KEY_0 -u GIT_CONFIG_VALUE_0 -u RTK_DB_PATH PATH="$PWD/.venv/bin:$PATH" npm test`: 1457 passed, 4 skipped; three existing asyncio deprecation warnings.
- `PATH="$PWD/.venv/bin:$PATH" npm run lint`: passed (documentation checks, Ruff, JavaScript syntax and Python compilation). No separate typecheck script is defined by this project.
- `CARGO_HOME=/tmp/cdx-ac08160c4b-cargo RUSTUP_HOME=/tmp/cdx-ac08160c4b-rustup PATH="/tmp/cdx-ac08160c4b-cargo/bin:$PATH" cargo test --manifest-path tray/Cargo.toml`: 99 passed; existing dead-code warnings. Rust was installed temporarily after the initial command found no Cargo.
- `npm pack --dry-run`: passed.
- `uv build --wheel --out-dir /tmp/cdx-ac08160c4b-wheels`: passed; the wheel includes the standalone collector module.
- `git diff --check`: passed.

The initial unadjusted `npm test` failed in temporary Git fixture repositories
and RTK history assertions because of inherited sandbox environment overrides.
The unadjusted lint found no system Ruff. Frozen development dependencies and
explicit subprocess environment selection resolved those validation failures;
no unrelated source changes or repository Git mutations were needed.
