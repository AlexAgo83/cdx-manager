## item_024_cli_robustness_tolerant_history_parsing_concurrent_removal_safe_status_clean_disk_view_fixes - CLI robustness: tolerant history parsing, concurrent-removal-safe status, clean/disk/view fixes
> From version: 0.10.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Low
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- One truncated JSONL line (crash mid-append) makes cdx history raise forever.
- cdx status crashes the whole table when a session is removed concurrently.
- Bare `cdx clean profiles` and `--old-logs=N` are misrouted as a session name; disk validates args after the expensive scan; view --json reports ok:true when the viewer cannot run.

# Scope
- In:
  - list_launch_history skips unparseable lines (matching run_usage._parse_json_records), optionally surfacing a skipped-lines count; consider extracting the tolerant parser into a shared fs_utils helper.
  - Wrap the per-session future.result() in status collection to skip or mark rows for sessions that vanished mid-scan.
  - Fix clean dispatch: leading `profiles` arg or any --tmp/--old-logs flag (including = form, via prefix split) routes to the profiles branch; bare `profiles` prints usage.
  - Hoist disk argument-combination validation above the first directory scan.
  - view --json sets ok:false and non-zero exit when viewer.failure is present.
  - Regression tests for each fix.
- Out:
  - New history/status features or output format changes beyond the failure contracts.

# Acceptance criteria
- A history file with a torn final line renders the remaining entries.
- Removing a session while status runs yields a table without that row, exit 0.
- `cdx clean profiles` prints usage; `cdx clean --old-logs=30` runs the profiles clean.
- `cdx disk --candidates <bad combo>` errors immediately without scanning.
- `cdx view --json` with logics-manager absent returns ok:false and non-zero exit.

# Report
- Launch history now skips unparseable JSONL lines and still returns valid entries.
- Status collection skips sessions that disappear during refresh instead of failing the whole table.
- `cdx clean profiles` without cleanup flags prints profile-clean usage, and `--old-logs=N` routes to profile cleanup.
- `cdx disk --candidates` validates the target before measuring disk usage.
- `cdx view --json` returns `ok:false` and exit 1 when `logics-manager` is unavailable.
- Validation: `python3 -m unittest discover -s test -p 'test_session_service_py.py'`; `python3 -m unittest discover -s test -p 'test_cli_py.py'`.

# AC Traceability
- request-AC5 -> This backlog slice. Proof: A history file with a torn final line renders the remaining entries.
- request-AC6 -> This backlog slice. Proof: Removing a session while status runs yields a table without that row, exit 0.
- request-AC7 -> This backlog slice. Proof: `cdx clean profiles` prints usage; `cdx clean --old-logs=30` runs the profiles clean.
- request-AC8 -> This backlog slice. Proof: `cdx disk --candidates <bad combo>` errors immediately without scanning.
- request-AC9 -> This backlog slice. Proof: `cdx view --json` with logics-manager absent returns ok:false and non-zero exit.
- request-AC14 -> This backlog slice. Proof: `cdx view --json` with logics-manager absent returns ok:false and non-zero exit.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_003_code_review_remediation_wave_2026_07`
- Architecture decision(s): (none yet)
- Request: `req_010_address_july_2026_code_review_findings_data_safety_reliability_and_cleanup`
- Primary task(s): `task_021_orchestrate_july_2026_code_review_remediation`

# AI Context
- Summary: CLI robustness: tolerant history parsing, concurrent-removal-safe status, clean/disk/view fixes
- Keywords: scaffolded-backlog, cli robustness: tolerant history parsing, concurrent-removal-safe status, clean/disk/view fixes, implementation-ready
- Use when: Implementing the scaffolded slice for CLI robustness: tolerant history parsing, concurrent-removal-safe status, clean/disk/view fixes.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
