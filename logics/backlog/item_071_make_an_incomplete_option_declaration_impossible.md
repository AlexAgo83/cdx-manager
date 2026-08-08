## item_071_make_an_incomplete_option_declaration_impossible - Make an incomplete option declaration impossible
> From version: 0.15.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 40%
> Complexity: Medium
> Theme: CLI surface
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Owner: claude

# Problem
- A flag can currently be declared in the parser table and omitted from the returned dict, which parses and validates and does nothing. That happened during 0.15.0 and only an integration test caught it.
- `_parse_flag_args` is already table-driven, so the mechanism exists; what is missing is that the table is not the only source of truth for an option.
- The same failure is expressible in the other direction: an option added to the settings validator but never displayed, or displayed but never mapped to a provider argument.

# Scope
- In:
  - Derive from one declaration whatever the measurement showed can be derived - parsing, the returned dict, usage text, the unset key set, the settings allow-list, and display.
  - Make an incomplete declaration fail at import or test time rather than at runtime, so the failure is loud and early.
  - Keep `cdx schema --json` deriving from the same definitions, with no second description of the same facts.
  - Add no runtime dependency.
  - Migrate existing options to the single declaration, one at a time, with the suite green between each.
- Out:
  - Adopting Typer, Click or any parsing framework.
  - Renaming options, changing their semantics, or altering any output.
  - Sites the measurement classified as genuine independent decisions, which stay where they are.

# Acceptance criteria
- AC1: Adding one option to `cdx set` requires one declaration, demonstrated by adding a throwaway option in a test.
- AC2: A declaration missing any derived site fails at import or in the suite, with a message naming what is missing.
- AC3: A flag present in the parser table but absent from the returned dict is no longer expressible, and a test demonstrates the failure mode is caught.
- AC4: `cdx schema --json` returns the same payload as before the migration for every existing option.
- AC5: No runtime dependency is added and the package manifests are unchanged.
- AC6: Every existing option behaves identically; the CLI contract tests pass unchanged.

# AC Traceability
- request-AC7 -> This backlog slice. Proof: AC1: Adding one option to `cdx set` requires one declaration, demonstrated by adding a throwaway option in a test.
- request-AC8 -> This backlog slice. Proof: AC2: A declaration missing any derived site fails at import or in the suite, with a message naming what is missing.
- request-AC9 -> This backlog slice. Proof: AC3: A flag present in the parser table but absent from the returned dict is no longer expressible, and a test demonstrates the failure mode is caught.
- request-AC10 -> This backlog slice. Proof: AC4: `cdx schema --json` returns the same payload as before the migration for every existing option.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_019_settle_0_15_0_s_remainder`
- Architecture decision(s): (none yet)
- Request: `req_029_settle_what_0_15_0_left_behind_before_cutting_0_15_1`
- Primary task(s): `task_040_settle_0_15_0_s_remainder_and_cut_0_15_1`

# AI Context
- Summary: Make an incomplete option declaration impossible
- Keywords: scaffolded-backlog, make an incomplete option declaration impossible, implementation-ready
- Use when: Implementing the scaffolded slice for Make an incomplete option declaration impossible.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
