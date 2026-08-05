## item_036_improve_unknown_session_guidance_for_cdx_config - Improve unknown-session guidance for cdx config
> From version: 0.12.1
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: CLI ergonomics
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- The config command’s generic unknown-session error does not tell operators how to discover or create the intended target.
- A broad shared-message change could unintentionally alter contracts for unrelated commands.

# Scope
- In:
  - Introduce command-scoped actionable error wording in `handle_config` or a narrowly scoped helper.
  - Preserve `CdxError` classification and JSON error envelope.
  - Add focused text/JSON/usage/success regression tests and update user-facing docs only if needed.
- Out:
  - Changing unknown-session messages for every CLI command.
  - Adding automatic session creation, fuzzy matching, or interactive prompts.

# Acceptance criteria
- AC1: Missing config session message includes the name and `cdx configs`/`cdx add` recovery guidance.
- AC2: JSON remains `unknown_session` with the improved message.
- AC3: Successful and invalid-syntax config behavior remain covered and unchanged.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Missing config session message includes the name and `cdx configs`/`cdx add` recovery guidance.
- request-AC2 -> This backlog slice. Proof: AC2: JSON remains `unknown_session` with the improved message.
- request-AC3 -> This backlog slice. Proof: AC3: Successful and invalid-syntax config behavior remain covered and unchanged.
- request-AC4 -> This backlog slice. Proof: AC3: Successful and invalid-syntax config behavior remain covered and unchanged.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_009_actionable_cdx_config_failures`
- Architecture decision(s): (none yet)
- Request: `req_016_clarify_cdx_config_errors_for_unknown_sessions`
- Primary task(s): `task_027_orchestrate_actionable_cdx_config_error_guidance`

# AI Context
- Summary: Improve unknown-session guidance for cdx config
- Keywords: scaffolded-backlog, improve unknown-session guidance for cdx config, implementation-ready
- Use when: Implementing the scaffolded slice for Improve unknown-session guidance for cdx config.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
