## req_041_make_accepted_cdx_tray_onboarding_and_updates_automatic - Make accepted CDX tray onboarding and updates automatic
> From version: 0.18.4
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Make accepted CDX tray onboarding and updates automatic
- Keywords: request-chain-scaffold, make accepted cdx tray onboarding and updates automatic, development-ready
- Use when: You need to implement or review the scaffolded workflow for Make accepted CDX tray onboarding and updates automatic.
- Skip when: The change is unrelated to this scaffolded request chain.

# Needs
- Installing the tray already downloads a verified companion, starts it, and asks about login startup, but it does not offer the related agent-alert consent in the same onboarding flow.
- A user who explicitly accepts startup and alerts expects the tray to remain useful without repeating setup for existing or newly created compatible sessions.
- cdx update already aligns an installed companion through staging and verification, but a running companion continues executing its old binary and requires a manual quit and relaunch.
- Automation must remain consent-based and recoverable: an install must never silently create startup behavior or enable alerts, and a failed restarted update must retain a working companion.

# Context
- src/commands/tray.py currently starts the tray after installation and asks only whether to enable autostart. Its --yes flag answers that one prompt, while non-interactive installs decline autostart.
- Per-session notify is intentionally opt-in. Hook provisioning happens on the next interactive launch, and Codex requires its own one-time hook trust approval per profile; CDX must not bypass that provider security boundary.
- src/commands/maintenance.py calls align_companion after a successful CDX update. The replacement is staged, checksummed, and probed before the old installed files are retired, but a live process is intentionally left running and only a restart-pending warning is emitted.
- src/tray_instance.py can identify a live tray lock owner. Any restart path must act only on that verified companion instance, wait within a short bound for it to exit, and never terminate an unrelated process from stale or malformed state.
- The earlier tray lifecycle request required explicit opt-in and rejected hidden background activation. This request preserves that decision by asking once at install; it only automates the behavior the user has explicitly accepted.

# Acceptance criteria
- AC1: An interactive cdx tray install asks separately and clearly whether to start at login and whether to enable agent alerts for compatible CDX sessions. Declining either leaves its current state unchanged.
- AC2: Accepting alerts enables notify for every existing supported session and records an explicit tray-owned default so newly created supported sessions inherit notify on. Unsupported providers remain unchanged.
- AC3: The install output and JSON result state whether the tray started, autostart was enabled, agent alerts were enabled, and whether Codex hook approval remains required. Non-interactive and JSON invocations never prompt; explicit flags select each consent deterministically.
- AC4: A user-initiated cdx update automatically stages, verifies, installs, and restarts a running tray companion. If no tray is running, it updates files without starting a new tray process.
- AC5: Restart acts only on a live CDX tray instance, uses a bounded graceful shutdown, verifies the replacement is running, and restores or retains a working companion when replacement launch fails. It never kills an unrelated process or reports success before the replacement is usable.
- AC6: A later cdx update does not repeat onboarding prompts and keeps accepted autostart and alert defaults. Explicit cdx tray autostart off and alert disabling remain reversible and effective.
- AC7: Focused tests cover every consent combination, existing and future supported sessions, non-interactive behavior, Codex trust notice, update with no tray, successful running-tray restart, stale lock, timeout, failed restart recovery, and no regression in staged-asset safety.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_030_accepted_automatic_cdx_tray_experience`
- Architecture decision(s): (none yet)

# References
- src/commands/tray.py
- src/commands/maintenance.py
- src/tray_install.py
- src/tray_instance.py
- src/tray_autostart.py
- src/agent_notify.py
- src/session_service.py
- test/test_tray_capability_py.py
- test/test_tray_contract_py.py
- logics/request/req_038_harden_cdx_tray_lifecycle_clarity_and_platform_validation.md

# Backlog
- `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`
