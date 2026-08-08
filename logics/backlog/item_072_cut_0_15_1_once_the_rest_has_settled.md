## item_072_cut_0_15_1_once_the_rest_has_settled - Cut 0.15.1 once the rest has settled
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

# Problem
- The `rate_limit_reached` fix is on main and unreleased. It corrects a false negative in `--failover`: an account with depleted credits but healthy percentage windows was reported as not exhausted, so a run that could not succeed was never migrated.
- It should not ship alone. Coupled with the registry lock fix it makes a patch release with real substance and avoids two releases in quick succession.
- 0.15.0's changelog states two known gaps. At least one has since changed, and a patch release that does not say so leaves the published record stale.

# Scope
- In:
  - Bump the three version declarations and the README badge.
  - Write `changelogs/CHANGELOGS_0_15_1.md`, stating which of 0.15.0's known gaps have closed and which remain.
  - Run the release gates through `logics-manager release plan` and `validate`, recording only evidence that has actually been observed.
  - Tag, publish, and record the post-publication evidence.
- Out:
  - Shipping the option-layer consolidation, which lands on its own schedule.
  - Flipping the background delegation default.

# Acceptance criteria
- AC1: 0.15.1 carries both the `rate_limit_reached` fix and the registry lock fix.
- AC2: The changelog states which of 0.15.0's known gaps have closed and which remain open.
- AC3: All nine release gates pass with evidence recorded only after the fact it describes was observed.
- AC4: npm and PyPI both report 0.15.1, verified at the registries rather than from workflow status alone.

# AC Traceability
- request-AC11 -> This backlog slice. Proof: AC1: 0.15.1 carries both the `rate_limit_reached` fix and the registry lock fix.
- request-AC2 -> This backlog slice. Evidence needed: The claim in `CHANGELOGS_0_15_0.md` that background delegation is off because it 'has been exercised far less' remains accurate, or is corrected if the closeout revision contradicts it.
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
- Summary: Cut 0.15.1 once the rest has settled
- Keywords: scaffolded-backlog, cut 0.15.1 once the rest has settled, implementation-ready
- Use when: Implementing the scaffolded slice for Cut 0.15.1 once the rest has settled.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_040_settle_0_15_0_s_remainder_and_cut_0_15_1`

# Notes
- Task `task_040_settle_0_15_0_s_remainder_and_cut_0_15_1` was finished via `logics-manager flow finish task` on 2026-08-09.
