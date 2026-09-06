## item_146_keychain_credential_portability_and_operator_recovery - Keychain credential portability and operator recovery
> From version: 0.20.9
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 95%
> Progress: 100%
> Complexity: High
> Theme: Operator workflow and runtime integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-06 12:25:45

# AI Context
- Summary: Carry the keychain credential in the bundle, clear a shadowing destination entry on import, and name the way out of the two message-only dead ends.
- Keywords: keychain, credential, portability, operator, recovery
- Use when: Working on bundle authentication or keychain error messages.
- Skip when: Working on Codex or Antigravity credential handling.

# Problem
`req_070` shipped `--include-auth` refusing keychain-backed profiles, and `req_071` left that decision plus two operator dead ends out of scope. The refusal makes `--include-auth` useless on exactly the profiles that matter, so this request reverses it and closes the dead ends before 0.20.9 ships.

# Scope
- In:
  - keychain credential export and import through the existing bundle schema
  - clearing a destination entry that would shadow an imported credential
  - the orphan-entry and oversized-credential messages
  - README and changelog wording
- Out:
  - native Security APIs for oversized credentials

# Acceptance criteria
- AC1: `cdx export --include-auth` includes a keychain-backed profile's credential, and `cdx import` restores a login that works.
- AC2: An import that carries a credential clears any keychain entry the destination profile already had, so the imported credential is the one in effect.
- AC3: The keychain wins over a stale credential file when both exist on export.
- AC4: A keychain that cannot be read is still an explicit error, in text and JSON, before anything is written.
- AC5: Refusing an orphan destination entry names the command that clears it, and an oversized credential error states that nothing changed and what to do instead.
- AC6: Operator documentation matches the new behavior.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: `cdx export --include-auth` includes a keychain-backed profile's credential, and `cdx import` restores a login that works.
- request-AC2 -> This backlog slice. Proof: AC2: An import that carries a credential clears any keychain entry the destination profile already had, so the imported credential is the one in effect.
- request-AC3 -> This backlog slice. Proof: AC3: The keychain wins over a stale credential file when both exist on export.
- request-AC4 -> This backlog slice. Proof: AC4: A keychain that cannot be read is still an explicit error, in text and JSON, before anything is written.
- request-AC5 -> This backlog slice. Proof: AC5: Refusing an orphan destination entry names the command that clears it, and an oversized credential error states that nothing changed and what to do instead.
- request-AC6 -> This backlog slice. Proof: AC6: Operator documentation matches the new behavior.

# Decision framing
- Product framing: Not needed
- Product signals: (none detected)
- Product follow-up: No product brief follow-up is expected based on current signals.
- Architecture framing: Not needed
- Architecture signals: (none detected)
- Architecture follow-up: No architecture decision follow-up is expected based on current signals.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_072_keychain_credential_portability_and_operator_recovery`
- Primary task(s): `task_081_keychain_credential_portability_and_operator_recovery`

# Priority
- Priority: High
- Rationale: `--include-auth` is useless on keychain-backed profiles until this ships, and 0.20.9 documents the opposite behavior.

# Notes
- Hybrid rationale: Derived from request `req_072_keychain_credential_portability_and_operator_recovery` and kept bounded to one coherent delivery slice.
- Source file: `logics/request/req_072_keychain_credential_portability_and_operator_recovery.md`.
- Generated locally by logics-manager.
- Task `task_081_keychain_credential_portability_and_operator_recovery` was finished via `logics-manager flow finish task` on 2026-09-06.

# Tasks
- `task_081_keychain_credential_portability_and_operator_recovery`
