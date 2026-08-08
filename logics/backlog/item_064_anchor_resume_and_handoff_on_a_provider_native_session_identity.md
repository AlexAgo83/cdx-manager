## item_064_anchor_resume_and_handoff_on_a_provider_native_session_identity - Anchor resume and handoff on a provider-native session identity
> From version: 0.14.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Session identity
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `get_resume_capability` at `src/provider_runtime.py:555` resolves resume to `codex resume --last --cd <cwd>` and `claude --continue`, both of which mean 'the most recent conversation in this directory'. Resuming therefore depends on the working directory and on no other session having run since.
- `handoff` reconstructs context by scraping the source session's terminal transcript. It is the only cross-provider transfer that exists and it works, but a terminal transcript is a weak anchor for anything that must run unattended.
- Claude's `--session-id <uuid>` and `--fork-session`, and Codex's `resume <id>` and `fork`, make identity-based resume available for the first time. Without adopting them, the failover this request builds would be founded on transcript scraping.

# Scope
- In:
  - Record a provider-native session identifier on the session record when the provider supplies or accepts one, for Codex and Claude only.
  - Extend `get_resume_capability` to report an identity-based strategy when an identifier is recorded, keeping the current recency strategy as the fallback.
  - Use the identifier in `_build_resume_spec` in place of `--continue` and `resume --last` when it is available.
  - Report the strategy actually chosen, and the reason, through `cdx can-resume --json`.
  - Use the identifier as the anchor for `handoff` where one exists, keeping transcript scraping for sessions that have none.
- Out:
  - Forking sessions (`--fork-session`, `codex fork`), which is a separate capability once identity exists.
  - Codex `archive`/`unarchive`/`delete` session management.
  - Removing transcript scraping, which remains the fallback for sessions without an identifier.
  - Any change to the ollama provider.

# Acceptance criteria
- AC1: After a launch, the session record carries the provider-native session identifier for Codex and Claude sessions where the provider exposes one.
- AC2: `cdx resume <name>` for a session with a recorded identifier resumes that exact conversation, and does so from a different working directory than the one it was launched in.
- AC3: `cdx resume <name>` still succeeds through the existing recency path for a session with no recorded identifier.
- AC4: `cdx can-resume <name> --json` names the strategy that will be used and distinguishes identity-based from recency-based.
- AC5: Launching an unrelated session in between does not change which conversation `cdx resume <name>` resumes.
- AC6: `handoff` uses the recorded identifier where one exists and falls back to transcript scraping where none does, with the source reported in its JSON payload.

# AC Traceability
- request-AC4 -> This backlog slice. Proof: AC1: After a launch, the session record carries the provider-native session identifier for Codex and Claude sessions where the provider exposes one.
- request-AC5 -> This backlog slice. Proof: AC2: `cdx resume <name>` for a session with a recorded identifier resumes that exact conversation, and does so from a different working directory than the one it was launched in.
- request-AC13 -> This backlog slice. Proof: AC3: `cdx resume <name>` still succeeds through the existing recency path for a session with no recorded identifier.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_018_executable_quota_routing`
- Architecture decision(s): (none yet)
- Request: `req_028_turn_quota_awareness_from_advice_into_execution_across_accounts_and_providers`
- Primary task(s): `task_039_orchestrate_executable_quota_routing_across_accounts_and_providers`

# AI Context
- Summary: Anchor resume and handoff on a provider-native session identity
- Keywords: scaffolded-backlog, anchor resume and handoff on a provider-native session identity, implementation-ready
- Use when: Implementing the scaffolded slice for Anchor resume and handoff on a provider-native session identity.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
