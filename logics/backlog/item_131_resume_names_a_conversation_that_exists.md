## item_131_resume_names_a_conversation_that_exists - Resume names a conversation that exists
> From version: 0.19.3
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 95%
> Progress: 100%
> Complexity: High
> Theme: Operator workflow and runtime integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-14 14:33:23

# AI Context
- Summary: Recorded after delivery: a resume minted a fresh conversation id and then resumed it, and the capability named conversations the provider never wrote.
- Keywords: resume, conversation id, can-resume, provider_continue, launch_session
- Use when: Changing how cdx resumes a provider conversation or reports resumability.
- Skip when: Changing token usage accounting.

# Problem
**Recorded after the fact.** Both defects were found and fixed while verifying the token-accounting work, and neither belonged to that request. This doc exists so the change has a record in a repository whose convention is that work is tracked, not to schedule work already done.
`cdx <session> --resume` was structurally broken for Claude. `handle_launch` called `launch_session` for resumes as well as launches, and that function mints a fresh conversation id for Claude on every call. The resume therefore minted a new id, stored it, and asked the provider to resume a conversation that had never existed -- `No conversation found with session ID` on every attempt, reproduced twice by the operator.
`get_resume_capability` reported `strategy: provider_conversation_id` whenever a stored id existed, without checking that the conversation did. A stored id survives any launch the provider never persisted, so `cdx can-resume` promised a resume that `cdx resume` then failed to perform.
`_build_resume_spec` computed that capability and then ignored it, rebuilding its arguments from the raw id. The JSON surface and the command actually run could therefore disagree -- reporting `provider_continue` while passing `--resume`.
The test covering the first defect enshrined it: it added a session, never launched it, and asserted the resume named a conversation id. That held only because the resume had just invented one.

# Scope
- In:
  - Skip the mint on the resume path, in `launch_session`, so both resume spellings inherit the fix.
  - Look the conversation up before naming it, reusing the transcript resolver built for usage extraction, and degrade to the provider's own fallback when it is missing.
  - Have the spec read the capability's decision rather than recomputing it.
  - Replace the test that enshrined the defect, and pin that a launch-then-resume carries the launch's own id.
- Out:
  - No change to how conversation ids are minted for launches.
  - No new resume strategy: both fallbacks already existed.

# Acceptance criteria
- Given a launched session, a resume carries that launch's conversation id and does not replace it.
- Given `cdx resume <name>` and `cdx <name> --resume`, both resume the same conversation the same way.
- Given a recorded conversation the provider never wrote, the capability reports `conversation_not_found` and the spec passes the fallback rather than the id.
- Given any of the above, `cdx can-resume --json` and the command actually run agree.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Given a launched session, a resume carries that launch's conversation id and does not replace it.
- request-AC2 -> This backlog slice. Proof: Given `cdx resume <name>` and `cdx <name> --resume`, both resume the same conversation the same way.
- request-AC3 -> This backlog slice. Proof: Given a recorded conversation the provider never wrote, the capability reports `conversation_not_found` and the spec passes the fallback rather than the id.
- request-AC4 -> This backlog slice. Proof: Given any of the above, `cdx can-resume --json` and the command actually run agree.
- request-AC5 -> This backlog slice. Proof: The tests assert the arguments the spec produced, not only the capability reported -- which is how the disagreement between the two was found -- and they write the transcript the real provider would have, instead of passing an id with nothing behind it.

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
- Request: `req_064_resume_names_a_conversation_that_exists`
- Primary task(s): `task_074_resume_names_a_conversation_that_exists`

# Priority
- Priority: Medium
- Rationale: Default until groomed.

# Notes
- Hybrid rationale: Derived from request `req_064_resume_names_a_conversation_that_exists` and kept bounded to one coherent delivery slice.
- Source file: `logics/request/req_064_resume_names_a_conversation_that_exists.md`.
- Generated locally by logics-manager.
- Task `task_074_resume_names_a_conversation_that_exists` was finished via `logics-manager flow finish task` on 2026-08-14.

# Tasks
- `task_074_resume_names_a_conversation_that_exists`
