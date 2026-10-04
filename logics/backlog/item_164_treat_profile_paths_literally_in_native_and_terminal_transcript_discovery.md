## item_164_treat_profile_paths_literally_in_native_and_terminal_transcript_discovery - Treat profile paths literally in native and terminal transcript discovery
> From version: 0.20.14
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 85%
> Complexity: Medium
> Theme: Filesystem portability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-10-04 17:34:02

# AI Context
- Summary: req_079 finding 2: authHome is embedded unescaped in glob patterns, so literal brackets hide valid transcripts. The timestamped terminal fallback uses the same pattern construction.
- Keywords: treat, profile, paths, literally, native, terminal, transcript, discovery
- Use when: Implementing treat profile paths literally in native and terminal transcript discovery.
- Skip when: Working outside this slice or adding deferred worktree management.

# Problem
- req_079 finding 2: authHome is embedded unescaped in glob patterns, so literal brackets hide valid transcripts. The timestamped terminal fallback uses the same pattern construction.

# Scope
- In:
  - Escape literal prefixes with standard-library glob.escape before adding wildcards, or reuse literal directory traversal; inspect related native/terminal discovery callers for the same root cause.
  - Cover both supported native provider layouts and timestamped terminal capture discovery, retaining legacy terminal log behavior.
  - Validate paths containing brackets and other filesystem-supported metacharacters; retain Windows-native separators and normalize workspace consistently.
  - No fallback to unrelated newest files; wrong source selection must still fail closed.
- Out:
  - No unrelated refactor, new service, or live provider/credential operation.

# Acceptance criteria
- AC1: Both native providers resolve an existing exact conversation beneath a profiles[team] directory.
- AC2: An explicit timestamped terminal capture beneath the same literal path is accepted as degraded recovery only when owned by the source.
- AC3: Metacharacter handling does not admit outside paths, nested subagents or unrelated workspace transcripts.

# AC Traceability
- request-AC9 -> This backlog slice. Proof deferred to implementation closeout; record the concrete regression and command result.
- request-AC10 -> This backlog slice. Proof deferred to implementation closeout; record the concrete regression and command result.
- request-AC11 -> This backlog slice. Proof deferred to implementation closeout; record the concrete regression and command result.
- request-AC12 -> This backlog slice. Proof deferred to implementation closeout; record the concrete regression and command result.

# Decision framing
- Product framing: Covered by the linked shared brief; this slice changes a user-visible reliability or reporting guarantee.
- Architecture framing: No separate ADR required; use existing persistence, transcript and CLI boundaries without a new subsystem.

# Links
- Product brief(s): `prod_056_trustworthy_local_recovery_and_usage_attribution`
- Architecture decision(s): (none yet)
- Request: `req_080_harden_reviewed_data_integrity_stats_accounting_and_handoff_recovery`
- Primary task(s): `task_085_orchestrate_review_hardening_across_persistence_stats_and_handoff`

# Priority
- Priority: Medium
- Rationale: restore handoff availability for valid profile paths without broadening file eligibility.

# Implementation entry points
- src/handoff.py and src/provider_runtime.py.

# Dependencies and sequencing
- After the High-priority wave; execute before item_163 exact-file selection.

# Validation plan
- Start with `node bin/python-runner.js -m pytest -q test/test_handoff_transcript_py.py test/test_commands_launch_py.py test/test_provider_runtime_helpers_py.py`.
- Add the smallest regression that fails on the reviewed defect; these existing suites alone are not proof of the fix.
- Finish with repository lint and the orchestration task cross-slice validation. Keep all fixture data synthetic and temporary.

# Implementation evidence
- Native and terminal discovery escape literal profile prefixes before adding glob wildcards. Native discovery also excludes symlink targets outside the source profile and retains existing subagent exclusions.
- `test_literal_profile_path_discovers_native_source` covers Codex and Claude under `profiles[team]`; `test_literal_profile_path_accepts_owned_terminal_capture` covers timestamped terminal fallback; the exact-path test rejects out-of-profile symlinks.
