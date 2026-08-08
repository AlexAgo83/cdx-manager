## item_072_cut_0_15_1_once_the_rest_has_settled - Cut 0.15.1 once the rest has settled
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
