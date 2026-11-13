## req_084_record_folder_trust_and_hook_approvals_before_every_cdx_launch - Record folder trust and hook approvals before every cdx launch
> From version: 0.27.1
> Schema version: 1.0
> Status: Ready
> Understanding: 95%
> Confidence: 90%
> Complexity: Medium
> Theme: launch-settings
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Before a launch, resume, handoff or shared-home headless run, cdx records the provider's folder trust (and, for Codex, approval of pending hooks) in that profile's own config, so an unattended agent never stops on a trust or hook-review prompt.
- Keywords: auto-trust-folder, auto-trust-hooks, folder trust, hasTrustDialogAccepted, trust_level, trustedWorkspaces, hooks.state, trusted_hash, hooks/list, config/batchWrite
- Use when: changing what cdx writes into a provider config before it starts, or a provider changes how it stores trust.
- Skip when: working on credentials, quotas or remote workers.

# Needs
- An agent launched through cdx must never stop on a folder-trust prompt or a hooks-trust/review prompt: nobody may be at the terminal.
- Folder trust and hook approval are two settings, both on by default, each of which the operator can turn off per session: `cdx set <name> --auto-trust-folder on|off` and `cdx set <name> --auto-trust-hooks on|off`.

# Context
- Claude Code asks "Do you trust the files in this folder?" and stores the answer as `projects[<folder>].hasTrustDialogAccepted` in `<profile home>/.claude.json` (Windows keys use forward slashes, `C:/Users/...`).
- Codex asks "Do you trust the contents of this directory?" and stores `[projects."<folder>"] trust_level = "trusted"` in `$CODEX_HOME/config.toml`. Its "Hooks need review" screen is answered by `[hooks.state."<hook key>"] trusted_hash` (plus `trusted_content_hash` for plugin hooks) in the same file. The hashes are Codex's own: `codex app-server` reports them through `hooks/list` (`currentHash`, `trustStatus` untrusted/modified/trusted) and persists edits through `config/batchWrite` with `upsert`. Checked against codex-cli 0.168.0.
- Codex also offers `--dangerously-bypass-hook-trust`; it skips trust for every hook of the invocation without persisting anything and is rejected by older Codex builds, so the persisted approval is preferred.
- Antigravity (agy 1.5.8) asks "Do you trust the contents of this project?" and stores `trustedWorkspaces` (a list of folders) in `<profile home>/.gemini/antigravity-cli/settings.json`.
- Providers may key a folder by the path as given or as resolved, so both spellings are recorded when they differ.
- Isolated runs start in a fresh sandbox home without the profile config, and remote runs execute on a worker, so neither writes into the controller profile.

# Acceptance criteria
- AC1: `cdx set <name> --auto-trust-folder on|off` and `--auto-trust-hooks on|off` persist two independent settings (keys `auto_trust_folder`, `auto_trust_hooks`); `cdx unset` clears them; unset means on; `cdx config <name>` and `cdx config <name> --json` show them.
- AC2: With `auto_trust_folder` on, an interactive launch, a resume, a handoff, a non-isolated headless run and a provider background run record the trust for their working folder in that session's provider config before the provider starts; with it off no folder trust is written.
- AC3: With `auto_trust_hooks` on, Codex approves every hook its app-server reports as untrusted or modified for that folder, after the folder trust so the project's own hooks are listed; cdx's own notification hooks are therefore approved too. Claude Code and Antigravity have no separate hook review (their hooks follow folder trust), so the setting changes nothing for them.
- AC4: Writes merge into the existing file (every other key and project is kept), happen only when something is missing, go through an atomic rename or the provider's own writer, and touch only the launched session's home; an unreadable file is left untouched and reported as a warning.
- AC5: Tests use fixture homes and a fake app-server: preservation of unrelated config, idempotence, each setting turned off on its own and both together, symlinked folders and per-profile isolation.
- AC6: A live check on Linux launches a Codex and an Antigravity profile in a new empty folder and sees no trust or hook prompt.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Risks
- Auto-trust runs a repository's own hooks and config without review. That is the requested trade-off for unattended agents; turning either setting off restores its prompt.
- A Codex launch spends about a second in a short-lived `codex app-server` to list hooks; a failure is a warning and the launch continues.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- `src/launch_trust.py`
- `src/codex_usage.py`
- `src/commands/launch.py`
- `test/test_launch_trust_py.py`

# Backlog
- none

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |
