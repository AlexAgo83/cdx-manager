## item_074_provision_and_revoke_provider_hooks_in_each_session_s_home_at_launch - Provision and revoke provider hooks in each session's home at launch
> From version: 0.15.1
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Notifications
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-09 17:16:24

# Problem
- The hook target is unreachable until each provider is told to call it, and that instruction lives in a configuration file per provider.
- Writing it into the user's real home would leak cdx's behavior into sessions cdx does not run, and would be a single global switch rather than a per-session one.
- Accounts created before this change must gain the behavior without the user running a migration, and a session whose notifications are turned off must lose it again.

# Scope
- In:
  - Write the Claude Code hook entries into `<authHome>/.claude/settings.json` and the Codex `notify` key into `<authHome>/config.toml` — Codex's home is `authHome` itself, since cdx sets `CODEX_HOME` to it directly, so there is no `.codex` segment on that path.
  - Write a hook command that resolves to cdx on every supported install path rather than the bare name `cdx`, reusing the `CDX_BIN` / `shutil.which` resolution `_scheduled_notify_argv` already performs, and accounting for the Windows npm install shipping a `cdx.cmd` shim that a direct (non-shell) spawn will not find under the bare name.
  - Merge into whatever the files already contain rather than overwriting them, leaving unrelated settings and user-authored hooks intact.
  - Make the write idempotent and recognizably cdx's own, so repeated launches change nothing and cdx can later remove exactly what it added.
  - Add a `--notify on|off` launch setting following the existing `--rtk` and `--logics` pattern, defaulting to on, and clearable through `cdx unset`.
  - When notifications are off for a session, remove the entries cdx wrote at that session's next launch, leaving everything else in place.
  - Treat an unwritable or malformed configuration file as a skipped provisioning step, never as a launch failure.
  - Document the behavior, the default, and the off switch in the README.
- Out:
  - No write to any path outside the session's own home directory.
  - No migration command and no provisioning outside the launch path.
  - No global on/off switch spanning all sessions beyond what the existing bulk settings flags already give.
  - No management of hook entries cdx did not write.
  - No addition of cdx to the user's PATH, and no installer change; the resolution happens at provisioning time and is baked into the written command.

# Acceptance criteria
- Given a session launched for the first time after this change, its own home contains the hook configuration for its provider, and no file outside that home has changed.
- Given the same session launched again, the configuration files are byte-identical to after the first launch.
- Given a session created before this change, its next launch provisions the configuration with no separate migration step.
- Given a configuration file already holding unrelated settings or user-authored hooks, those survive provisioning unchanged.
- Given a new session with no notification setting, notifications are enabled.
- Given `cdx set <name> --notify off` followed by a launch of that session, the entries cdx wrote are gone and any other content in the files remains.
- Given a configuration file that cannot be written or cannot be parsed, the launch proceeds normally and the provider still starts.
- Given a Codex session, the `notify` key is written to `<authHome>/config.toml` and Codex reads it, rather than to a `.codex` subdirectory Codex never looks at.
- Given a Windows npm install where `cdx` is a `.cmd` shim, the provisioned hook command still invokes cdx when the provider spawns it directly rather than through a shell.
- Given an install where cdx is absent from the PATH the provider inherits, the provisioned hook command still resolves.
- The README states that notifications are on by default, shows the command that turns them off, and states the per-platform delivery caveats.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: Given a session launched for the first time after this change, its own home contains the hook configuration for its provider, and no file outside that home has changed.
- request-AC3 -> This backlog slice. Proof: Given the same session launched again, the configuration files are byte-identical to after the first launch.
- request-AC4 -> This backlog slice. Proof: Given a session created before this change, its next launch provisions the configuration with no separate migration step.
- request-AC5 -> This backlog slice. Proof: Given a configuration file already holding unrelated settings or user-authored hooks, those survive provisioning unchanged.
- request-AC5 -> This backlog slice. Proof: Given a new session with no notification setting, notifications are enabled.
- request-AC10 -> This backlog slice. Proof: Given a Windows npm install where `cdx` is a `.cmd` shim, the provisioned hook command still invokes cdx when the provider spawns it directly rather than through a shell.
- request-AC12 -> This backlog slice. Proof: The README states that notifications are on by default, shows the command that turns them off, and states the per-platform delivery caveats.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_020_know_which_parallel_session_needs_you`
- Architecture decision(s): (none yet)
- Request: `req_030_tell_the_user_which_parallel_cdx_session_finished_or_is_waiting_without_watching_terminals`
- Primary task(s): `task_041_orchestrate_agent_completion_notifications`

# AI Context
- Summary: Provision and revoke provider hooks in each session's home at launch
- Keywords: scaffolded-backlog, provision and revoke provider hooks in each session's home at launch, implementation-ready
- Use when: Implementing the scaffolded slice for Provision and revoke provider hooks in each session's home at launch.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
