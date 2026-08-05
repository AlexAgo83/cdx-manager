## item_040_preserve_local_plugin_state_during_force_import - Preserve local plugin state during force import
> From version: 0.12.3
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: Medium
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `import_bundle()` replaces the entire existing session profile directory on `--force`; that directory contains more than credentials, including locally installed Codex plugins such as `ponytail`.
- The current authless guard from `item_022` only runs when `include_auth` is false. In the issue #7 scenario the bundle includes auth, so `allow_authless_force` is irrelevant and local plugin state is still discarded.
- The success path deletes `backup_root` after writing bundle files, so any plugin state not present in the bundle is unrecoverable after the command completes.

# Scope
- In:
  - Identify the smallest set of local profile paths that must be preserved for installed Codex plugins. Start with the concrete `plugins` path under the session profile; include adjacent plugin manager metadata only if tests or local Codex plugin layout prove it is required for `codex plugin add` installs to survive.
  - Before mutating an existing session in force mode, inspect `session_root` for those local plugin-state paths and record the paths that exist.
  - After the bundle profile has been written and before deleting `backup_root`, restore the recorded plugin-state paths from `backup_root` into the new `session_root` when the bundle did not provide those same paths.
  - If a preserved path conflicts with a bundle-provided path, keep the bundle path and report the conflict only if that would discard a locally installed plugin; choose the simpler behavior that keeps credentials replacement intact.
  - If copying/restoring any required plugin-state path fails, call the existing `_restore_import_backup()` path and raise a controlled `CdxError` that names the session and failed path.
  - Update CLI help and README import documentation to say that `--force` preserves detected local plugin state and that `--include-auth` only controls credential payloads.
  - Add focused service/CLI regression tests for an auth-bearing force import over a session with a local plugin marker, selected-session behavior, and no regression to the authless `--allow-authless-force` guard.
- Out:
  - No new bundle format, manifest, or `--include-plugins` export option.
  - No automatic plugin reinstall from marketplace URLs.
  - No broad preservation of all cache/temp directories; keep temporary clone/backup caches disposable.
  - No change to merge-mode local-file precedence.
  - No implementation work in this scaffold-only task.

# Acceptance criteria
- Given an existing session profile containing `plugins/ponytail` (or the locally correct plugin marker path) and a valid bundle for the same session with `include_auth: true` but no plugin files, `import_bundle(..., force=True)` leaves that plugin marker present after success.
- Given the same bundle and a session excluded by `session_names`, the excluded session profile remains byte-for-byte untouched for the plugin marker path.
- Given a forced auth-bearing import where plugin-state restoration fails, the command raises `CdxError`, restores the original profile from backup, restores the old session record/state, and does not delete local plugin state.
- Given an authless bundle over an existing session, `import_bundle(..., force=True, allow_authless_force=False)` still raises the existing explicit credentials refusal before any plugin preservation work.
- Given merge mode, existing local files keep their current behavior and the new plugin preservation path is not needed.
- CLI help and README clearly separate auth payload preservation from local plugin preservation and reference the force import behavior.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Given an existing session profile containing `plugins/ponytail` (or the locally correct plugin marker path) and a valid bundle for the same session with `include_auth: true` but no plugin files, `import_bundle(..., force=True)` leaves that plugin marker present after success.
- request-AC2 -> This backlog slice. Proof: Given the same bundle and a session excluded by `session_names`, the excluded session profile remains byte-for-byte untouched for the plugin marker path.
- request-AC3 -> This backlog slice. Proof: Given a forced auth-bearing import where plugin-state restoration fails, the command raises `CdxError`, restores the original profile from backup, restores the old session record/state, and does not delete local plugin state.
- request-AC4 -> This backlog slice. Proof: Given an authless bundle over an existing session, `import_bundle(..., force=True, allow_authless_force=False)` still raises the existing explicit credentials refusal before any plugin preservation work.
- request-AC5 -> This backlog slice. Proof: Given merge mode, existing local files keep their current behavior and the new plugin preservation path is not needed.
- request-AC6 -> This backlog slice. Proof: CLI help and README clearly separate auth payload preservation from local plugin preservation and reference the force import behavior.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_010_force_import_preservation_for_local_plugin_state`
- Architecture decision(s): (none yet)
- Request: `req_020_prevent_cdx_import_force_from_silently_discarding_local_plugins`
- Primary task(s): `task_031_orchestrate_force_import_plugin_preservation`

# AI Context
- Summary: Preserve local plugin state during force import
- Keywords: scaffolded-backlog, preserve local plugin state during force import, implementation-ready
- Use when: Implementing the scaffolded slice for Preserve local plugin state during force import.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_031_orchestrate_force_import_plugin_preservation`

# Notes
- Task `task_031_orchestrate_force_import_plugin_preservation` was finished via `logics-manager flow finish task` on 2026-08-05.
