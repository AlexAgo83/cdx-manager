## item_068_correct_the_req_028_record_to_state_what_background_delegation_was_actually_verified_to_do - Correct the req_028 record to state what background delegation was actually verified to do
> From version: 0.15.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
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
- request-AC3 -> This backlog slice. Evidence needed: Twenty concurrent writers to the run registry all succeed on Windows, with no `OSError` reaching the caller, and `test_concurrent_starts_do_not_lose_records` passes on a real Windows machine rather than only in CI.
- request-AC4 -> This backlog slice. Evidence needed: Lock acquisition behaves equivalently on both platforms under contention - a waiter waits rather than failing - and the difference between `LK_LOCK`'s bounded retry and `flock`'s indefinite block is either removed or documented as deliberate.
- request-AC5 -> This backlog slice. Evidence needed: A caller that cannot acquire the lock within a bounded time receives a specific, actionable error rather than a raw `OSError`, so an exhausted wait is distinguishable from a bug.
- request-AC6 -> This backlog slice. Evidence needed: The option layer's touch points are measured and published - which declarations are independent decisions and which are mechanical restatements of the same fact - before any consolidation design is chosen.
- request-AC7 -> This backlog slice. Evidence needed: Adding one option to `cdx set` requires one declaration, and a declaration that is incomplete fails loudly at import or test time rather than producing a flag that parses and does nothing.
- request-AC8 -> This backlog slice. Evidence needed: `cdx schema --json` still derives its enums, mutually-exclusive groups and error codes from the same definitions the parser uses, with no second description of the same facts.
- request-AC9 -> This backlog slice. Evidence needed: No runtime dependency is added.
- request-AC10 -> This backlog slice. Evidence needed: The regression that motivated this - a flag present in the parser table but absent from the returned dict - is impossible to express, and a test demonstrates that the failure mode is now caught.

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

# Tasks
- `task_040_settle_0_15_0_s_remainder_and_cut_0_15_1`

# Notes
- Task `task_040_settle_0_15_0_s_remainder_and_cut_0_15_1` was finished via `logics-manager flow finish task` on 2026-08-09.
