## req_072_keychain_credential_portability_and_operator_recovery - Keychain credential portability and operator recovery
> From version: 0.20.9
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 95%
> Complexity: Medium
> Theme: Profile data safety and authentication
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-09-06 12:25:44

# AI Context
- Summary: Make keychain-backed Claude authentication portable through bundles and give the operator a way out of the two remaining keychain dead ends.
- Keywords: export, import, bundle, keychain, portability, recovery
- Use when: Working on bundle authentication or keychain error messages.
- Skip when: Working on Codex or Antigravity credential handling.

# Needs
- `req_070` shipped `--include-auth` refusing keychain-backed profiles, and `req_071` left that decision plus two operator dead ends out of scope. The refusal makes `--include-auth` useless on exactly the profiles that matter, so this request reverses it and closes the dead ends before 0.20.9 ships.

# Context
- Supersedes the scope decision recorded in `req_070` AC4: keychain portability is delivered, not refused.
- The keychain entry holds the same document Claude Code otherwise writes to `claude-home/.claude/.credentials.json`, so the bundle needs no new schema — the entry travels under that path.
- A destination profile can hold its own keychain entry, which takes precedence over the credential file at runtime; an import that does not clear it would silently keep the wrong login.
- The two dead ends are message-only: an orphan destination entry the operator cannot name, and an oversized credential with no stated way forward.
- Out of scope: native Security APIs. The transfer ceiling stays, with an error that now says what to do instead.

# Acceptance criteria
- AC1: `cdx export --include-auth` includes a keychain-backed profile's credential, and `cdx import` restores a login that works.
- AC2: An import that carries a credential clears any keychain entry the destination profile already had, so the imported credential is the one in effect.
- AC3: The keychain wins over a stale credential file when both exist on export.
- AC4: A keychain that cannot be read is still an explicit error, in text and JSON, before anything is written.
- AC5: Refusing an orphan destination entry names the command that clears it, and an oversized credential error states that nothing changed and what to do instead.
- AC6: Operator documentation matches the new behavior.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_053_safe_profile_operations_with_isolated_claude_keychain_authentication`
- Architecture decision(s): (none yet)

# References
- `src/session_backup.py`
- `src/claude_credentials.py`
- `test/test_profile_data_safety_py.py`
- `README.md`

# Backlog
- `item_146_keychain_credential_portability_and_operator_recovery`
