## task_074_resume_names_a_conversation_that_exists - Resume names a conversation that exists
> From version: 0.19.3
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 95%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-14 14:33:23

# AI Context
- Summary: Recorded after delivery: both resume defects were found while verifying the token-accounting work and fixed there.
- Keywords: resume, conversation id, can-resume, retrospective, 0.20.0
- Use when: Revisiting this change.
- Skip when: Working on unrelated cdx surfaces.

# Definition of Done (DoD)
- [x] The backlog scope is implemented.
- [x] Acceptance criteria are covered.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# Backlog
- `item_131_resume_names_a_conversation_that_exists`

# Acceptance criteria
- Given a launched session, a resume carries that launch's conversation id and does not replace it.
- Given `cdx resume <name>` and `cdx <name> --resume`, both resume the same conversation the same way.
- Given a recorded conversation the provider never wrote, the capability reports `conversation_not_found` and the spec passes the fallback rather than the id.
- Given any of the above, `cdx can-resume --json` and the command actually run agree.

# Plan
- [x] 1. Skip the conversation mint on the resume path in `launch_session`, so both spellings inherit it.
- [x] 2. Look the conversation up before naming it, reusing the transcript resolver, and degrade to `--continue` / `resume --last` when it is absent.
- [x] 3. Have `_build_resume_spec` read the capability rather than rebuilding its arguments from the raw id.
- [x] 4. Replace the test that enshrined the defect and pin both spellings against their own launch.
- [x] GATE: delivered, validated, and shipped in 0.20.0.

# AC Traceability
- request-AC1 -> This task. Proof: `test_resume_carries_the_conversation_the_launch_created` asserts the resumed id equals the launch's and that the stored conversation is unchanged. 2e708ad
- request-AC2 -> This task. Proof: `test_the_two_resume_spellings_are_the_same_resume` runs both forms and pins each to its own launch. a984379
- request-AC3 -> This task. Proof: `test_a_recorded_conversation_the_provider_never_wrote_is_not_offered` and `test_a_resume_spec_falls_back_when_the_conversation_is_gone`. 313bee4
- request-AC4 -> This task. Proof: `test_a_resume_whose_conversation_vanished_falls_back_instead_of_failing` asserts the reported strategy and the spawned arguments together. 313bee4
- request-AC5 -> This task. Proof: The tests assert the produced command, which is how the capability/spec disagreement surfaced, and write the transcript the real provider would have rather than passing a bare id. 313bee4

# Validation
- 2026-08-14: `npm test` 968 passed, `npm run lint` all checks passed, GitHub CI green on Linux, macOS and Windows.
- On the operator's real store, `cdx can-resume` reports `provider_conversation_id / supported` for the Claude and Codex sessions that carry a conversation, after having failed with `No conversation found with session ID` on every attempt beforehand.
- command: `npm test && npm run lint` | result: passed | date: 2026-08-14
- Finish workflow executed on 2026-08-14.
- Linked backlog/request close verification passed.

# Report
- Delivered in 2e708ad, 313bee4 and a984379; shipped in 0.20.0.
- Both defects were found while verifying the token-accounting work, not by the tests: the operator ran `cdx <session> --resume` twice and got the provider's raw failure both times.
- The test that should have caught the first defect encoded it -- it added a session, never launched it, and asserted the resume named a conversation id, which only held because the resume had just invented one.
- A second defect surfaced while fixing the first: `_build_resume_spec` computed the capability and then ignored it, so the JSON surface and the command run could disagree. Only a test asserting the produced arguments could see that.
- Finished on 2026-08-14.
- Linked backlog item(s): `item_131_resume_names_a_conversation_that_exists`
- Related request(s): `req_064_resume_names_a_conversation_that_exists`

# Links
- Request: `req_064_resume_names_a_conversation_that_exists`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
