## item_048_make_the_priority_setting_count_in_next_status_and_ready - Make the priority setting count in next, status, and ready
> From version: 0.13.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Session selection
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `cdx set <name> --priority 90` currently changes only `cdx select` and `cdx run --provider`. `cdx next`, the `cdx status` recommendation line, and `cdx ready` ignore it.
- Status rows do not carry the setting at all, so the recommendation ranking could not honor it even if it wanted to.
- `cdx next` prints a `Priority:` line derived from `_priority_instruction`, which describes the recommendation ranking rather than the `--priority` value. A user tuning `--priority` and checking `cdx next` sees an unchanged line labelled 'Priority' and has no signal that the two are unrelated.

# Scope
- In:
  - Carry the session's configured priority through to the status rows the recommendation path consumes.
  - Weigh it in the unified ranking so it affects `cdx next`, the `cdx status` recommendation, and `cdx ready` alongside the existing factors.
  - Decide and document where priority sits relative to availability and reset tiering — specifically whether a high-priority session that is currently unusable outranks a usable low-priority one, which is the case that determines whether the setting feels honored or ignored.
  - Resolve the naming collision between the user-set `--priority` and the recommendation ranking in user-facing output, so a `Priority:` line and the `--priority` setting no longer name different concepts.
  - Document in the README what `--priority` actually influences, now that the answer is 'every selection command' rather than 'some of them'.
  - Add tests asserting that raising one session's priority changes the winner reported by `cdx next`, `cdx status`, and `cdx ready`, and that an unset priority behaves exactly as today.
- Out:
  - No change to the accepted range or validation of `--priority`.
  - No automatic priority assignment or inference.
  - No per-command priority overrides.

# Acceptance criteria
- Given two otherwise-equal sessions where one has a higher `--priority`, `cdx next` names the higher-priority session.
- Given the same pair, the `cdx status` recommendation and `cdx ready` name that same session.
- Given no session with an explicit priority, the ordering reported by every affected command is unchanged from current behavior.
- Given a high-priority session that is currently unusable and a usable lower-priority one, the documented rule is applied and a test asserts the expected winner by name.
- No user-facing output uses the word priority for both the `--priority` setting and the recommendation ranking without distinguishing them.
- The README states which commands `--priority` influences and how it combines with availability and resets.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: Given two otherwise-equal sessions where one has a higher `--priority`, `cdx next` names the higher-priority session.
- request-AC6 -> This backlog slice. Proof: Given the same pair, the `cdx status` recommendation and `cdx ready` name that same session.
- request-AC8 -> This backlog slice. Proof: Given no session with an explicit priority, the ordering reported by every affected command is unchanged from current behavior.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_012_one_session_selection_rule_across_every_command`
- Architecture decision(s): (none yet)
- Request: `req_022_unify_the_two_divergent_session_selection_rankings_into_one_contract`
- Primary task(s): `task_033_orchestrate_the_unified_session_selection_ranking`

# AI Context
- Summary: Make the priority setting count in next, status, and ready
- Keywords: scaffolded-backlog, make the priority setting count in next, status, and ready, implementation-ready
- Use when: Implementing the scaffolded slice for Make the priority setting count in next, status, and ready.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
