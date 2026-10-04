## req_077_review_findings_cross_process_memory_writes_and_early_import_recovery - Review findings: cross-process memory writes and early import recovery
> From version: 0.20.14
> Schema version: 1.0
> Status: Obsolete
> Understanding: 95
> Confidence: 95
> Complexity: Medium
> Theme: Data integrity
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Two reproduced residual data-integrity defects remain after earlier hardening: memory append locks cover threads but not CLI processes, and a force import moves the live profile before a keychain read outside rollback protection.
- Keywords: audit, memory, multiprocessing, append, force import, keychain, rollback
- Use when: Assessing follow-up work on accepted memory writes or failed backup imports.
- Skip when: Changing provider features, pricing, or tray presentation.

# Needs
- P1: A failed force import must preserve the existing live profile when its initial credential read fails.
- P2: Concurrent successful memory appends from separate CLI processes must retain every accepted note.
- Capture only: these are candidates for follow-up work, not a delivery commitment or authorization to implement.

# Priority
- High: a failed import can leave a registered session without its live profile; parallel memory writers can silently lose accepted notes.

# Context
- Reviewed revision: `47d36cc` (version 0.20.14), on 2026-10-04; the working tree was initially clean.
- Inspected CLI memory dispatch, session and run stores, filesystem helpers, backup encryption/import/export, credential failure handling, tray installation/update recovery, viewer actions, package configuration, and CI. Ran the full local Python and Rust suites and repository checks.
- This is a targeted repository audit, not exhaustive line-by-line verification. Native Windows/Linux behavior, real credential stores, live provider calls, published artifact installation, and dependency vulnerability databases were not exercised.
- Earlier review req_073 was superseded by req_074, whose delivery includes item_147 and item_148. These findings identify residual gaps in that completed work, rather than repeating the already-fixed late credential rollback and thread concurrency cases.

## Finding 1 — Early credential failure leaves the live profile displaced (P1)
- Evidence: `src/session_backup.py:315-343` creates recovery data and renames the existing session root at line 323. The credential read at line 343 can raise before entering the rollback-protected block at line 346.
- Real failure sources: `src/claude_credentials.py:48-68` raises on timeout, unavailable/denied keychain access, or malformed credentials.
- Reproduction executed with temporary files and a simulated keychain error: create an existing session with a profile sentinel; produce an encrypted bundle containing the credential file; call `import_bundle(..., force=True)` while making `read_keychain_credentials` raise `CdxError`.
- Observed: import raises; the original live profile no longer exists; the session record still points at that absent path. The sentinel survives in the temporary import recovery directory, inside its profile subdirectory.
- Impact: a refused import disrupts an existing session and requires manual recovery. This is displacement, not demonstrated permanent data loss. The error does not report the retained recovery directory.
- Existing coverage: `test/test_profile_data_safety_py.py:251` tests a later failure after credential deletion, and line 278 tests failed credential restoration. Neither covers the initial credential read after the directory move.
- Candidate correction: complete the fallible credential preflight before moving the live profile, or extend rollback protection to include it. Preserve recovery diagnostics if restoration itself fails.

## Finding 2 — Memory append serialization does not cross process boundaries (P2)
- Evidence: `src/context_store.py:109-133` uses a process-local dictionary of `threading.Lock` objects around read-modify-write. Both context and memory CLI append handlers call this helper (`src/commands/context_memory.py`).
- Reproduction executed: use two multiprocessing workers and a shared barrier immediately after each worker's real `read_context_path` call, then run the unchanged append/write functions against one temporary file. The barrier deterministically schedules the same overlap that independent CLI processes can encounter.
- Observed: both processes exit 0; the file contains `initial` and `note-A`, with `note-B` missing. Which note survives is scheduling-dependent.
- Impact: agents invoking separate CLI commands can silently overwrite an accepted note. Atomic replacement prevents a torn file but does not serialize a read-modify-write across processes.
- Existing coverage: `test/test_context_store_py.py:117-149` uses threads in one interpreter. That validates the current lock without exercising the actual independent-process boundary.
- Candidate correction: serialize through a shared filesystem lock and validate with independent processes. No new memory service or speculative abstraction is needed.

## Validation observed
- `rtk npm run lint`: passed, including JavaScript syntax, project documentation, Ruff, and Python compilation.
- `rtk npm run test:coverage`: 1,058 passed in 22.14 seconds on macOS / Python 3.11.15; total statement-and-branch coverage reported as 83%.
- `rtk cargo test --manifest-path tray/Cargo.toml`: 104 passed.
- `rtk npm run release:validate`: checksum validation passed for 0.20.14; this alone does not establish release readiness.
- `rtk npm pack --dry-run`: passed; no package was published or installed.
- Before capture: `logics-manager status` reported no open workflow docs; `health --format json` reported 397 documents and zero issues; `audit --group-by-doc` and `lint --require-status` passed.
- Both reproductions used temporary synthetic data. No production credential access, provider generation, or application code changes were made.

# Acceptance criteria
- AC1: A denied initial credential read during force import leaves the original profile, session record, and state usable; a regression exercises this exact failure point.
- AC2: At least two independent processes appending to the same memory file retain the initial content and every successfully accepted note, including a controlled overlapping-read scenario.
- AC3: Follow-up fixes retain existing backup/credential and memory behavior and pass the relevant regression suites and repository lint.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- `src/session_backup.py`
- `src/context_store.py`
- `src/claude_credentials.py`
- `test/test_profile_data_safety_py.py`
- `test/test_context_store_py.py`

# Backlog
- none

# Links
- Superseded by: `req_080_harden_reviewed_data_integrity_stats_accounting_and_handoff_recovery`
