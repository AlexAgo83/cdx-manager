## prod_054_recoverable_cdx_operations_across_credentials_runs_and_tray_interop - Recoverable CDX operations across credentials, runs, and tray interop
> Date: 2026-09-07
> Status: Settled
> Related request: `req_074_harden_review_findings_for_credential_safety_process_lifecycle_and_tray_interop`
> Related backlog: `item_147_preserve_credentials_and_portable_encrypted_backups`
> Related task: `task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.
> Indicators reviewed: 2026-09-07 09:59:28

# Overview
Turn reproduced review findings into bounded fixes that keep authentication, local writes, provider processes, and tray launch surfaces recoverable across macOS, Windows, and WSL.

```mermaid
flowchart LR
  Review[req_073 reproduced findings] --> Request[req_074 hardening request]
  Request --> Credentials[item_147 credentials and backups]
  Request --> Runs[item_148 writes and run lifecycle]
  Request --> Tray[item_149 tray install recovery]
  Request --> WSL[item_150 Windows to WSL interop]
  Credentials --> Gates[focused tests plus project validation]
  Runs --> Gates
  Tray --> Gates
  WSL --> Gates
```

# Goals
- Preserve user credentials and backup readability during import, force rollback, and runtime changes.
- Keep background runs and local memory writes under deterministic CDX ownership.
- Make tray updates recoverable and tray actions truthful across native Windows, macOS, and Windows-hosted WSL.
- Validate the repaired paths with small regressions plus the existing project gates.

# Non-goals
- No provider generation, live credential mutation, release publication, UI redesign, or broad tray feature expansion.
- No new dependency unless an existing standard or installed primitive cannot provide the needed locking, process cleanup, or path handling.
- No claim of universal Linux desktop support beyond the scoped WSL and existing tray capability contracts.

# Scope and guardrails
- In: scaffolded request, product, backlog, orchestration task, validation, and handoff context.
- Out: unrelated workflow docs and implementation of generated tasks.

# Key product decisions
- Use structured input as the source of truth for generated docs.
- Keep generated write paths local and repo-bounded.

# Success signals
- Generated docs pass lint and audit without broad manual rewrites.
- Context-pack output can be handed to an implementation agent directly.

# References
- Product back-reference: `item_147_preserve_credentials_and_portable_encrypted_backups`
- Task back-reference: `task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop`
