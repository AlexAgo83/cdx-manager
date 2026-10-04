## req_079_review_findings_handoff_source_ambiguity_and_literal_profile_paths - Review findings: handoff source ambiguity and literal profile paths
> From version: 0.20.14
> Schema version: 1.0
> Status: Obsolete
> Understanding: 95
> Confidence: 95
> Complexity: Medium
> Theme: Handoff reliability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Reproduced handoff source-selection ambiguity and glob metacharacter failures despite the existing exact-transcript regression suite passing.
- Keywords: handoff, transcript, identity, ambiguity, selection, glob, paths
- Use when: Reviewing exact source resolution and interactive candidate selection.
- Skip when: Changing usage accounting, pricing, or provider authentication.

# Needs
- P2: Detect multiple eligible transcripts for an identity and preserve the exact candidate explicitly selected by the operator.
- P2: Treat profile-directory names literally during transcript discovery, including paths containing glob metacharacters.
- Capture only: findings are candidates for follow-up, with no implementation or delivery chain committed.

# Priority
- Medium: one edge case can launch recovery from the wrong history; another prevents otherwise valid handoffs. Neither reproduction required real provider execution or credentials.

# Context
- Reviewed revision: `47d36cc`, version 0.20.14, on 2026-10-04. Existing review requests req_077 and req_078 were preserved.
- Traced source discovery, identity/workspace inspection, explicit candidate selection, preparation and pointer writes, source-byte validation on reuse, prompt generation, and target launch dispatch.
- Compared with completed req_075 and its acceptance criteria, especially AC2 requiring ambiguous identity to produce explicit selection rather than an automatic choice.
- Scope: local code and synthetic transcripts on macOS. No private conversation contents or credentials read; no model execution and no claim that the target agent actually obeys the recovery prompt.

## Finding 1 — Duplicate identities defeat exact selection (P2)
- Evidence: `src/handoff.py:156-170` accepts the single path returned by conversation_transcript without checking for other eligible files with the same identity. `src/provider_background.py:194-211` returns the first filename match during os.walk; the native rollout lookup in `src/interactive_usage.py:155-168` similarly returns the first match.
- The interactive chooser compounds this: `src/commands/launch.py:442` discards the selected candidate's path and resolves only its conversation_id again. The menu itself prints identity/workspace/time, not the path distinguishing duplicate candidates.
- Reproduction executed: create two valid native conversation files in separate project directories, with the same conversation ID and normalized workspace but different content/digests. Discovery reports two candidates and two digests; resolve_source returns one without reporting ambiguity.
- Then remove the recorded identity, invoke the real handoff handler, and select the candidate for the other file through its numbered menu. The handler returns 0 and reaches the target-launch boundary once, but the prepared entry names the first resolver match rather than the selected file. Target launch was mocked; all selection and preparation code was real.
- Impact: copied or divergent transcript files sharing an identity can yield recovery from unintended history even after an explicit operator choice. Which path is selected depends on filesystem traversal order, not validated uniqueness.
- Candidate correction: enumerate and validate eligible identity/workspace matches; reject ambiguity for identity-only requests. Preserve and revalidate the exact path/descriptor selected through the menu. An explicit native disambiguation path must also be available to non-interactive callers.
- Coverage gap: current fixtures exercise distinct identities and wrong modification times, not multiple eligible paths sharing one identity.

## Finding 2 — Literal brackets in profile paths break discovery (P2)
- Evidence: `src/handoff.py:29-34` interpolates authHome directly into glob patterns. A literal directory component containing brackets is interpreted as a character class instead of a directory name.
- Reproduction executed for both native providers: create valid transcripts below a temporary directory named profiles[team], preserving the correct native identity and workspace. The source file exists and is readable; resolve_source fails with no candidates and reports that the conversation is missing or not top-level.
- Even if the native os.walk resolver finds the file, the handoff rejects it because it is absent from the glob-generated eligible paths list.
- Impact: a valid home/CDX_HOME location can make every native handoff fail. Explicit conversation ID does not bypass the faulty eligible-path check.
- Related caller: `src/provider_runtime.py:511-521` similarly interpolates its log directory into a glob for timestamped terminal captures, so the degraded fallback has the same literal-path concern; the reproduced cases here cover native discovery.
- Candidate correction: escape only the literal directory prefix using the standard library before adding intended wildcards, or traverse directories without pattern interpretation. No dependency or custom escaping layer is needed.
- Coverage gap: existing path tests check Windows separators but not literal glob metacharacters.

## What the current implementation does well
- Normal source selection is identity- and workspace-bound, with no silent modification-time fallback.
- Top-level eligibility and metadata reject unrelated workspaces, sidechains, malformed complete records, and unsupported native source formats.
- Preparation preserves the full original transcript, including tool evidence, rather than replacing it with a truncated textual summary; partial final JSONL is excluded from the measured extent.
- Private unique entry files isolate concurrent preparations. Failed pointer replacement preserves the prior pointer and removes the newly orphaned entry.
- Reuse checks the prepared byte extent and digest, tolerates later appends, and refuses deletion, truncation, or rewriting rather than silently degrading to shared notes.
- Recovery instructions require repository instructions, bounded historical reading, current-state verification, and an explicit checkpoint. Historical tool output is evidence, not fresh authorization.
- Shared notes and authentication remain separate from automatic transcript preparation. JSON mode prepares without launching.

## Limits that should remain explicit
- The source transcript remains a live external dependency, not a copied recovery archive. Keep it available until recovery is complete; the README already documents this.
- The receiving agent's comprehension, permission to read the source, and compliance with the recovery sequence are not proven by prompt construction. Existing tests prove preparation/dispatch behavior, not a successful live recovery.
- The one-name command uses the latest pointer for that target/workspace; each already-dispatched launch carries its own unique entry path. This is documented behavior, not a race finding.

## Validation observed
- `rtk proxy node bin/python-runner.js -m pytest -q test/test_handoff_transcript_py.py test/test_commands_launch_py.py test/test_context_store_py.py`: 76 passed in 1.89 seconds.
- Duplicate-identity reproduction used real discovery/resolution and the real handoff handler with only the target-launch boundary mocked.
- Literal-bracket reproduction ran both native provider resolvers against temporary valid transcripts.
- No application code or tracked tests were modified.

# Acceptance criteria
- AC1: Multiple eligible files with one conversation identity yield explicit ambiguity; identity-only requests never silently select an arbitrary path.
- AC2: Interactive selection of a candidate prepares that exact validated file, with path-level diagnostics allowing duplicate identities to be distinguished.
- AC3: Valid native handoffs work beneath directories with literal brackets and other supported glob metacharacters, while still excluding invalid or unrelated sources.
- AC4: Existing preparation, byte-integrity, instruction-ordering, authentication-isolation, and no-launch-on-error regressions remain green.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- `src/handoff.py`
- `src/commands/launch.py`
- `src/provider_background.py`
- `src/interactive_usage.py`
- `test/test_handoff_transcript_py.py`
- `README.md`

# Backlog
- none

# Links
- Superseded by: `req_080_harden_reviewed_data_integrity_stats_accounting_and_handoff_recovery`
