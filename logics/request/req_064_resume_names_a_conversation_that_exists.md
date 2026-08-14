## req_064_resume_names_a_conversation_that_exists - Resume names a conversation that exists
> From version: 0.19.3
> Schema version: 1.0
> Status: Done
> Understanding: 95
> Confidence: 90
> Complexity: Medium
> Theme: Session lifecycle
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-14 14:33:23

# AI Context
- Summary: A resume minted a fresh conversation id and then asked the provider to resume it, and the capability named conversations that were never written -- both fixed; recorded here because the work had no home.
- Keywords: resume, conversation id, can-resume, provider_continue, launch_session, retrospective
- Use when: Changing how cdx resumes a provider conversation or reports resumability.
- Skip when: Changing token usage accounting.

# Needs
- **Recorded after the fact.** Both defects were found and fixed while verifying the token-accounting work, and neither belonged to that request. This doc exists so the change has a record in a repository whose convention is that work is tracked, not to schedule work already done.
- `cdx <session> --resume` was structurally broken for Claude. `handle_launch` called `launch_session` for resumes as well as launches, and that function mints a fresh conversation id for Claude on every call. The resume therefore minted a new id, stored it, and asked the provider to resume a conversation that had never existed -- `No conversation found with session ID` on every attempt, reproduced twice by the operator.
- `get_resume_capability` reported `strategy: provider_conversation_id` whenever a stored id existed, without checking that the conversation did. A stored id survives any launch the provider never persisted, so `cdx can-resume` promised a resume that `cdx resume` then failed to perform.
- `_build_resume_spec` computed that capability and then ignored it, rebuilding its arguments from the raw id. The JSON surface and the command actually run could therefore disagree -- reporting `provider_continue` while passing `--resume`.
- The test covering the first defect enshrined it: it added a session, never launched it, and asserted the resume named a conversation id. That held only because the resume had just invented one.
# Context
- Claude accepts a caller-supplied `--session-id`, so cdx mints one per launch and stores it (`_conversation_identity_for_launch`, `src/session_service.py:817`). The docstring is explicit that a launch starts a new conversation and the stored value is always the newest -- which is right for launches and exactly wrong for resumes.
- Both resume spellings converge on the same call: `cdx resume <name>` through `handle_resume`, and `cdx <name> --resume` through the bare-name fallthrough in `src/cli.py:625`. A fix to one silently leaves the other broken unless it lands in the shared path.
- Checking whether a conversation exists became cheap only after the token-accounting request built transcript resolution by conversation id. This request reuses that resolver rather than adding a second way to answer the same question.
- Each provider already had a fallback for "no known conversation": `claude --continue` and `codex resume --last`. The defect was never a missing strategy, only a failure to reach the one that applied.
# Delivery
- Delivered in 2e708ad (a resume carries the conversation it is resuming), 313bee4 (resumability checked before the conversation is named, and the spec reads the same decision), and a984379 (both resume spellings pinned to the same behaviour). Shipped in 0.20.0.
- Validated with `npm test` (968 passed at the time) and `npm run lint`; `cdx can-resume` on the operator's real store reports `provider_conversation_id / supported` for the two Claude and Codex sessions that carry a conversation, and GitHub CI is green on Linux, macOS and Windows.
- No backlog slice or task exists because the work predates this record. That is the point of the doc: the change had no home, and a repository whose convention is that work is tracked should not carry a fix nobody can find.

# Acceptance criteria
- AC1: A resume carries the conversation it is resuming; no new conversation id is minted on the resume path.
- AC2: Both `cdx resume <name>` and `cdx <name> --resume` resume the same conversation the same way.
- AC3: A recorded conversation the provider never wrote is not offered as a named resume; the capability degrades to the provider's own fallback and reports `conversation_not_found`.
- AC4: What `cdx can-resume --json` reports and what `cdx resume` actually runs agree, because both read the same decision.
- AC5: Tests assert the command produced, not only the capability reported, and stop passing an id with nothing on disk behind it.
# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- src/session_service.py
- src/provider_runtime.py
- src/commands/launch.py
- src/cli.py
- test/test_commands_launch_py.py
- test/test_runtime_py.py

# Backlog
- `item_131_resume_names_a_conversation_that_exists`
