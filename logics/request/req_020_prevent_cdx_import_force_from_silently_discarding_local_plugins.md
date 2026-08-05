## req_020_prevent_cdx_import_force_from_silently_discarding_local_plugins - Prevent cdx import force from silently discarding local plugins
> From version: 0.12.3
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# Needs
- `cdx import <bundle> --force --sessions <names>` must not silently discard locally installed Codex plugins, skills, memories, or other non-auth profile state when overwriting an existing session.
- The issue is distinct from `item_022`: `item_022` guards credentials only when a force import bundle lacks auth (`include_auth` false), while GitHub issue #7 occurs with an auth-bearing bundle (`--include-auth` present), so the existing `--allow-authless-force` guard never runs.
- Users need either preservation or an explicit, actionable warning before destructive replacement of local plugin state, because the operation is commonly used for credential refresh and the plugin loss is discovered only after a later `cdx update all` or launch check.

# Context
- In `src/session_service.py`, `import_bundle()` computes conflicts, then only refuses destructive force imports when `conflicts and force and not decoded["meta"].get("include_auth") and not allow_authless_force`.
- For each existing session imported with `force`, `import_bundle()` captures the old record/state, renames the whole `session_root` to `backup_root`, sets `is_existing = False`, creates a fresh `session_root`, writes the bundle record/state, and writes only files present in `decoded_profiles`; on success the backup is removed in `finally`.
- Because the whole previous profile directory is replaced, local directories such as `plugins`, `skills`, `memories`, marketplace caches, and plugin manager state are lost unless they are included in the bundle payload. Auth inclusion does not imply plugin inclusion.
- GitHub issue #7 reports this exact path on 2026-08-05: after running `cdx import <bundle> --force --sessions claw,corvus,digital,gemi,matcha,olla,rose,tapion,work1,work2,work3,work4,work5,work6` from an auth refresh bundle, all `work*` sessions lost the locally installed `ponytail` plugin even though `main` was excluded and remained intact.
- `cdx update all --yes` can reinstall `ponytail`, but that recovery is manual and plugin-specific; import should not make a silent destructive change to local non-auth state.

# Acceptance criteria
- AC1: A force import over an existing session with an auth-bearing bundle preserves installed local plugin state by default, including at least a `plugins` directory representing a plugin installed via `codex plugin add`, when the bundle does not include that plugin state.
- AC2: If preservation cannot be performed for a detected local plugin/non-auth state path, `cdx import --force` fails before mutating the session and reports the affected session and path; no backup is deleted and the existing profile remains intact.
- AC3: The existing `item_022` credential safety behavior remains unchanged: auth-less force imports are still refused unless `--allow-authless-force` is passed, corrupt bundle entries still roll back per session, and auth files from an auth-bearing bundle still replace the intended credential files.
- AC4: `cdx import --merge` semantics are unchanged: local files that already exist continue to win, and this request does not turn merge into force or force into merge.
- AC5: The CLI output/help/README document the force-import behavior precisely: auth-bearing bundles restore credentials but do not inherently carry local plugins, and force import preserves or refuses to discard detected plugin state rather than silently removing it.
- AC6: Focused tests demonstrate the issue #7 scenario: an existing session with a local `plugins` marker and a valid auth-bearing bundle for the same session survives `import --force`, and a selected session outside `--sessions` remains untouched.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_010_force_import_preservation_for_local_plugin_state`
- Architecture decision(s): (none yet)

# References
- https://github.com/AlexAgo83/cdx-manager/issues/7
- src/session_service.py
- src/cli_args.py
- src/cli_commands.py
- src/update_all.py
- src/cli_helpers.py
- README.md
- test/test_session_service_py.py
- test/test_cli_py.py
- logics/backlog/item_022_safe_bundle_import_pre_validation_credential_guard_per_session_rollback.md

# AI Context
- Summary: Prevent cdx import force from silently discarding local plugins
- Keywords: request-chain-scaffold, prevent cdx import force from silently discarding local plugins, development-ready
- Use when: You need to implement or review the scaffolded workflow for Prevent cdx import force from silently discarding local plugins.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_040_preserve_local_plugin_state_during_force_import`
