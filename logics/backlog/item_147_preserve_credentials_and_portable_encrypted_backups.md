## item_147_preserve_credentials_and_portable_encrypted_backups - Preserve credentials and portable encrypted backups
> From version: 0.20.9
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Data integrity
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-07 09:28:51

# AI Context
- Summary: Implements the credential and backup-format slice for req_073 findings 1-3: keychain-only merge preservation, late force-import credential rollback, and recorded-KDF encrypted bundle decoding.
- Keywords: req_073, session_backup, backup_bundle, keychain-only profile, force import rollback, PBKDF2, scrypt, KDF portability
- Use when: Changing import/export credential handling or encrypted backup decoding.
- Skip when: The work is about runs, memory append locking, tray updates, or Windows-to-WSL tray actions.

# Problem
- Merge and rollback can replace or lose a keychain-only local account, and bundle decryption can ignore the exporter-recorded KDF.

# Scope
- In:
  - Fix credential-backend collision handling for merge imports.
  - Snapshot and restore original keychain credentials when force import fails after credential staging.
  - Decode encrypted bundles according to a validated stored KDF with a defined legacy fallback.
  - Add focused tests for keychain-only merge, late force rollback, and PBKDF2-to-scrypt runtime portability.
- Out:
  - No credential migration between real accounts, no live keychain mutation outside isolated tests, and no cryptographic format redesign beyond recorded-KDF correctness.

# Acceptance criteria
- AC1: Merge import preserves an existing keychain-only destination credential and reports the retained local account behavior.
- AC2: Late force-import failure restores credential, files, record, and state or reports incomplete recovery.
- AC3: PBKDF2 fallback bundles decode on a scrypt-capable runtime with the same passphrase, with legacy behavior covered by tests.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Merge import preserves an existing keychain-only destination credential and reports the retained local account behavior.
- request-AC2 -> This backlog slice. Proof: AC2: Late force-import failure restores credential, files, record, and state or reports incomplete recovery.
- request-AC3 -> This backlog slice. Proof: AC3: PBKDF2 fallback bundles decode on a scrypt-capable runtime with the same passphrase, with legacy behavior covered by tests.
- request-AC13 -> This backlog slice. Proof: AC3: PBKDF2 fallback bundles decode on a scrypt-capable runtime with the same passphrase, with legacy behavior covered by tests.
> Shared proof: request-AC3 and request-AC13 share the same final validation wave for this slice.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_054_recoverable_cdx_operations_across_credentials_runs_and_tray_interop`
- Architecture decision(s): (none yet)
- Request: `req_074_harden_review_findings_for_credential_safety_process_lifecycle_and_tray_interop`
- Primary task(s): `task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
