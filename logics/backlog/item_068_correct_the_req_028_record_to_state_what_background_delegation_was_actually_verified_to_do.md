## item_068_correct_the_req_028_record_to_state_what_background_delegation_was_actually_verified_to_do - Correct the req_028 record to state what background delegation was actually verified to do
> From version: 0.15.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 80%
> Complexity: Low
> Theme: Release hygiene
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Owner: claude
> Indicators reviewed: 2026-08-09

# Problem
- `req_028`'s closeout records AC11 as `unverified` and describes background delegation as disabled rather than shipped broken. Both were true when written and neither is true now.
- It was subsequently made to work and verified end to end against a live account: the agent identified from the `backgrounded - <id>` line, completion read from the provider's session transcript rather than from agent state, usage and final answer recovered, and the parked session stopped.
- A traceability document that understates verification is the same defect as one that overstates it. This project spent a release insisting the difference between `tested` and `observed` be stated; the record has to hold in both directions or the distinction is decorative.

# Scope
- In:
  - Rewrite the AC11 proof to state what was observed, when, and what remains unexercised.
  - State that delegation is opt-in for exposure - one account, one prompt shape - and not because it is known broken.
  - Check `CHANGELOGS_0_15_0.md` against the revised record and correct it if the two now disagree.
  - Re-baseline indicators and re-run `flow validate`.
- Out:
  - Flipping the delegation default, which is a separate decision with its own evidence bar.
  - Re-cutting or amending the 0.15.0 release notes.

# Acceptance criteria
- AC1: The AC11 proof names the observation - launch, closeout with usage from the session transcript, session stopped - rather than reporting the criterion as unverified.
- AC2: The record states why delegation stays opt-in, distinguishing limited exposure from known breakage.
- AC3: `CHANGELOGS_0_15_0.md` and the closeout record agree.
- AC4: `flow validate` reports no findings and the audit stays at zero blocking.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: The AC11 proof names the observation - launch, closeout with usage from the session transcript, session stopped - rather than reporting the criterion as unverified.
- request-AC2 -> This backlog slice. Proof: AC2: The record states why delegation stays opt-in, distinguishing limited exposure from known breakage.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_019_settle_0_15_0_s_remainder`
- Architecture decision(s): (none yet)
- Request: `req_029_settle_what_0_15_0_left_behind_before_cutting_0_15_1`
- Primary task(s): `task_040_settle_0_15_0_s_remainder_and_cut_0_15_1`

# AI Context
- Summary: Correct the req_028 record to state what background delegation was actually verified to do
- Keywords: scaffolded-backlog, correct the req_028 record to state what background delegation was actually verified to do, implementation-ready
- Use when: Implementing the scaffolded slice for Correct the req_028 record to state what background delegation was actually verified to do.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
