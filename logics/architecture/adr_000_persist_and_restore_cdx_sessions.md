## adr_000_persist_and_restore_cdx_sessions - Persist and restore cdx sessions
> Date: 2026-04-15
> Status: Accepted
> Drivers: Persistent login state, explicit recovery, local privacy, predictable session reuse, per-session provider isolation.
> Related request: `req_XXX_example`
> Related backlog: `item_001_persistent_codex_session_storage_and_rehydration`
> Related task: `task_000_persistent_codex_session_storage_and_rehydration`
> Reminder: Update status, linked refs, decision rationale, consequences, migration plan, and follow-up work when you edit this doc.

# Overview
Persist session metadata locally and isolate provider credentials inside per-session auth homes.
Restore sessions explicitly when `cdx <name>` is launched, and fail with a clear recovery path when the saved state is missing, expired, or revoked.
This keeps named sessions reusable across terminal restarts without silently guessing the user identity.

```mermaid
flowchart LR
    Current[No durable session reuse] --> Decision[Local metadata plus isolated per-session auth homes]
    Decision --> App[CLI session flow]
    Decision --> Data[Session records and recovery state]
    Decision --> Ops[User-facing recovery and cleanup]
    Decision --> Team[Implementation and tests]
```

# Context
The product needs named sessions that survive process exit and terminal restarts.
The main constraint is that the user must not be silently rebound to the wrong account if stored state becomes stale or corrupted.
We also want the storage approach to be portable across local development environments and simple enough to reason about during support and debugging.
These drivers point toward a local-first model with a clear separation between session metadata and provider-managed auth material.

# Decision
Store session metadata in a local JSON registry and keep provider credentials inside isolated per-session auth directories (`CODEX_HOME` for Codex, `HOME` for Claude).
Rehydration is explicit: a saved session is restored only when the user launches that named session.
If the saved state is invalid, the CLI stops with a concise recovery message rather than attempting a hidden fallback.

# Alternatives considered
- Plain text metadata and credentials in one local file: simplest to implement, but mixes session registry and provider-owned auth material too tightly.
- Remote account storage: unnecessary for a single-terminal local workflow and worse for privacy and offline use.
- Metadata only without isolated auth homes: would not satisfy the requirement to keep accounts separated per named session.

# Consequences
- The CLI can relaunch sessions without forcing a fresh login on every use.
- The implementation must handle expiry, revocation, and corruption as first-class states.
- Support becomes easier because the source of truth is local and deterministic.
- Session isolation is stronger because each named session has its own provider auth home and logs.

# Migration and rollout
- Start with a new local storage format for new sessions.
- Keep recovery behavior explicit so failures are visible instead of silent.
- If a future storage migration is needed, add a dedicated migration step before changing the on-disk format.

# References
- `logics/backlog/item_001_persistent_codex_session_storage_and_rehydration.md`

# Follow-up work
- Implement session metadata persistence and per-session provider auth isolation.
- Add validation and recovery paths for expired, revoked, and missing session state.
- Add tests for save, restore, delete, and failure scenarios.
