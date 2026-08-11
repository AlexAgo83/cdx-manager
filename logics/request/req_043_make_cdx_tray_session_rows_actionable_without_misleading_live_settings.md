## req_043_make_cdx_tray_session_rows_actionable_without_misleading_live_settings - Make CDX tray session rows actionable without misleading live settings
> From version: 0.18.4
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Tray usability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Make CDX tray session rows actionable without misleading live settings
- Keywords: request-chain-scaffold, make cdx tray session rows actionable without misleading live settings, development-ready
- Use when: You need to implement or review the scaffolded workflow for Make CDX tray session rows actionable without misleading live settings.
- Skip when: The change is unrelated to this scaffolded request chain.

# Needs
- The compact, capacity-first session row is becoming the natural control point for each CDX session, not merely a status label.
- A native tray row cannot safely mean both 'launch immediately' and 'choose one of several actions'. The current direct launch must therefore become an explicit session action menu.
- CDX model, reasoning, permission, working-directory, and terminal-launch choices are launch settings. Presenting them as live edits for an already running session would promise a retroactive effect that does not exist.
- The future Logics tray integration needs a clear place for declared session-aware actions, without hard-coded placeholders or arbitrary plugin shell commands.

# Context
- tray/src/menu.rs currently makes every session row ActionId::Session(index), and macOS, Windows, and Linux all resolve it by opening a terminal on cdx <session>.
- The shared tray model already owns text labels and action identifiers, while macOS custom cells draw the capacity gauge but must retain an accessible native text fallback for Windows and Linux.
- cdx config <name> reports a session's pinned launch configuration. The cdx set aliases update persistent launch settings for a later launch; they do not mutate an existing provider process in place.
- req_040 owns the globally capacity-sorted row order and provider context. req_037 owns the versioned Logics plugin snapshot, declared action ids, and safe plugin routing; this request must compose with both rather than duplicate them.

# Acceptance criteria
- AC1: Selecting a rendered session row opens one native per-session action submenu on macOS, Windows, and supported Linux instead of launching ambiguously from the summary row; the displayed row, submenu, and target session retain the same stable identity after capacity reordering.
- AC2: Every available session submenu contains an explicit Open session action that preserves today's best-effort terminal launch behavior, plus a View launch configuration action that opens cdx config <session> through the same native or WSL command path as the tray status command.
- AC3: The tray never presents model, reasoning, permission, working-directory, terminal-title, or similar launch settings as a live change to a running session. Any future-launch configuration entry is explicitly labelled as applying to the next launch and does not silently restart, stop, or reconfigure a provider process.
- AC4: The shared menu/action contract can carry a bounded set of declared session extension actions, but the base tray renders no empty Extensions or Logics placeholder. Logics actions appear only when the existing plugin contract declares supported, validated actions and remain subject to its no-arbitrary-shell-routing boundary.
- AC5: Unsupported, unavailable, stale, disabled, or malformed session and extension actions are omitted or visibly disabled with a reason; they cannot launch a different session, run an arbitrary command, or break the base status and alert menu.
- AC6: Focused tests cover row-to-submenu identity across interleaved providers and reorders, explicit Open session routing, native/WSL configuration-view routing, omission of retroactive settings and absent extensions, and preservation of existing gauges, alert history, global actions, and accessible fallback text.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_032_actionable_cdx_tray_session_controls`
- Architecture decision(s): (none yet)

# References
- src/tray_contract.py
- src/cli.py
- src/cli_args.py
- src/commands/status.py
- src/commands/settings.py
- src/session_service.py
- tray/src/menu.rs
- tray/src/runner.rs
- tray/src/backend.rs
- tray/src/mac.rs
- tray/src/win.rs
- tray/src/linux.rs
- tray/src/mac_cell.rs
- logics/request/req_037_add_a_first_party_logics_plugin_surface_to_the_cdx_tray.md
- logics/request/req_040_keep_the_cdx_tray_menu_globally_ordered_by_remaining_capacity.md
- tray/Cargo.toml

# Backlog
- `item_090_add_an_explicit_capability_safe_action_submenu_to_every_tray_session_row`
