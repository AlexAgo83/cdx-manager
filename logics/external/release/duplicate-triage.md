# Duplicate Triage

Generated: 2026-05-29

## Detector Result

Command:

```bash
python logics/skills/logics-duplicate-detector/scripts/find_duplicates.py --min-score 0.55
```

The detector reports similarity between core-session, auth-management, status-overview, spec, and product docs. These are expected Logics traceability overlaps rather than merge candidates.

## Decisions

- Keep `item_000_cdx_core_session_manager` and `item_005_cdx_session_auth_management` separate: the first owns the launch/list/add/remove command surface, while the second owns login, logout, onboarding, and session-scoped credential isolation.
- Keep `task_001_cdx_core_session_manager` and `task_005_cdx_session_auth_management` separate for the same implementation-boundary reason.
- Keep `item_004_cdx_status_global_session_overview`, `task_002_cdx_status_global_session_overview`, and `spec_001_cdx_status_overview` separate: backlog captures scope, task captures delivery, and spec captures behavior/output contract.
- Keep product brief overlaps with backlog/tasks: product docs describe product framing and user value, while backlog/tasks carry acceptance and execution details.

## Release Impact

No merge or deletion is required before release. The overlap is a documentation hygiene warning, not a release blocker.
