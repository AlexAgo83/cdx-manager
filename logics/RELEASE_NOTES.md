# Release Notes

## 0.6.5

`cdx-manager` 0.6.5 is release-ready from the Logics gate perspective.

### Highlights

- Added the headless `cdx run --json` execution contract for Orchestia.
- Added deterministic `cdx select --json` session selection and reused it from provider-based headless runs.
- Normalized provider-neutral `--reasoning-effort` handling while keeping `--power` as a compatibility alias.
- Added transcript/stdout/stderr artifact paths, nullable usage fields, timeout handling, and stable cdx/provider error source reporting.
- Preserved the existing multi-session CLI behavior, auth isolation, status overview, installers, and packaging surfaces.

### Validation

- `npm run lint`
- `npm test`
- `python -m unittest discover -s test -p 'test_*_py.py'`
- `python logics/skills/logics.py lint --require-status`
- `python logics/skills/logics-release-gatekeeper/scripts/release_gate_check.py`
- `python logics/skills/logics-release-gatekeeper/scripts/release_gate_check.py --require-release-notes`
- `python -m unittest discover -s logics/skills/tests -p 'test_*.py'`
- `npm audit --omit=dev`
- `python -m pip check`
- `npm pack --dry-run`
- `python -m build --sdist --wheel`

### Rollback

If a release issue appears, roll back the headless automation slices in reverse order: artifact/usage reporting, reasoning-effort mapping, automatic selection, then the base headless JSON run command. Existing interactive session-management flows can remain available while the headless integration is paused.
