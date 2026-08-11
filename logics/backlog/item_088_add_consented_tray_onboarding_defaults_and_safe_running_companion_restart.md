## item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart - Add consented tray onboarding defaults and safe running-companion restart
> From version: 0.18.4
> Schema version: 1.0
> Status: Ready
> Understanding: 92%
> Confidence: 78%
> Progress: 0%
> Complexity: High
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Add consented tray onboarding defaults and safe running-companion restart
- Keywords: scaffolded-backlog, add consented tray onboarding defaults and safe running-companion restart, implementation-ready
- Use when: Implementing the scaffolded slice for Add consented tray onboarding defaults and safe running-companion restart.
- Skip when: The change belongs to another backlog slice.

# Problem
- A user must currently perform separate lifecycle and per-session notification setup, then manually restart a running tray after every companion update.
- Naively killing and relaunching a process after replacement risks stopping an unrelated process or losing a known-working tray when the new build cannot start.
- The existing promotion order in `src/tray_install.py` is already the Windows-safe one, but it has only ever run against a stopped companion; a directory holding a running executable is expected to refuse the rename.
- No graceful shutdown channel exists: `tray/src/instance.rs` records a pid and proves liveness, and nothing more.

# Scope
- In:
  - Add explicit interactive and flag-driven install consent for autostart and agent alerts, with truthful text and JSON outcomes.
  - Persist a tray alert default and apply it to existing and future Codex and Claude sessions only; preserve each provider's normal hook provisioning and trust flow.
  - Extend the staged companion update transaction with verified, bounded restart of a known running tray and recovery when launch fails.
  - Keep install, autostart off, alert off, no-running-tray update, and unavailable platform paths idempotent and recoverable.
  - Add focused platform-boundary tests and concise documentation for the one-time consent and Codex approval caveat.
- Out:
  - Changing direct notification delivery, agent alert content, tray menu behavior, quota data, or provider-owned approval policies.
  - Automatic updates outside a user-initiated cdx update, startup without consent, or relaunching a tray that was intentionally quit.
  - Operating-system administrator installation, network services, arbitrary process control, or provider hook trust bypass.

# Acceptance criteria
- AC1: Install makes both durable choices explicit and applies only accepted choices to the correct current and future sessions.
- AC2: A running known companion is safely restarted to the verified replacement after cdx update, while a stopped companion remains stopped.
- AC3: A failed stop, wait, or replacement launch leaves an honest diagnostic and a recoverable working state rather than an unverified success.
- AC4: Regression tests cover consent, provider scope, trust messaging, lifecycle reversibility, update restart, and staged-update rollback.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Install makes both durable choices explicit and applies only accepted choices to the correct current and future sessions.
- request-AC2 -> This backlog slice. Proof: AC2: A running known companion is safely restarted to the verified replacement after cdx update, while a stopped companion remains stopped.
- request-AC3 -> This backlog slice. Proof: AC3: A failed stop, wait, or replacement launch leaves an honest diagnostic and a recoverable working state rather than an unverified success.
- request-AC4 -> This backlog slice. Proof: AC4: Regression tests cover consent, provider scope, trust messaging, lifecycle reversibility, update restart, and staged-update rollback.
- request-AC5 -> This backlog slice. Proof: AC4: Regression tests cover consent, provider scope, trust messaging, lifecycle reversibility, update restart, and staged-update rollback.
- request-AC6 -> This backlog slice. Proof: AC4: Regression tests cover consent, provider scope, trust messaging, lifecycle reversibility, update restart, and staged-update rollback.
- request-AC7 -> This backlog slice. Proof: AC4: Regression tests cover consent, provider scope, trust messaging, lifecycle reversibility, update restart, and staged-update rollback.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed, but constrained by `adr_006_tray_menu_lifecycle_observation_boundary`: a Windows companion showing its menu processes nothing, so the bounded shutdown wait must survive an open menu without escalating to a kill.

# Links
- Product brief(s): `prod_030_accepted_automatic_cdx_tray_experience`
- Architecture decision(s): (none yet)
- Request: `req_041_make_accepted_cdx_tray_onboarding_and_updates_automatic`
- Primary task(s): `task_052_orchestrate_accepted_automatic_cdx_tray_onboarding_and_updates`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
