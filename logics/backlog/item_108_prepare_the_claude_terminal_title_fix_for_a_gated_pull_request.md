## item_108_prepare_the_claude_terminal_title_fix_for_a_gated_pull_request - Prepare the Claude terminal-title fix for a gated pull request
> From version: 0.18.6
> Schema version: 1.0
> Status: Obsolete
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: release-delivery
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 22:15:30

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: prepare, claude, terminal, title, fix, gated, pull, request
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- The completed change currently resides as uncommitted work on main, which is not reviewable or safely pushable as-is.
- A release-facing user fix needs an intentional version decision and aligned metadata before it enters review.
- Opening a PR before the multi-platform CI result would make an unvalidated state externally visible.

# Scope
- In:
  - Inspect the worktree, base commit, remotes, existing release conventions, and changed files before any write or external action.
  - Create a narrowly named feature branch from the verified main base and commit only the title-fix implementation plus its required docs and Logics artifacts.
  - Choose the next patch version by default for this backward-compatible bug fix; stop for operator direction if inspection shows a breaking or release-policy reason to choose otherwise.
  - Update every repository-owned version declaration and the changelog or release-note surface used by this repository, then make a separate release-preparation commit if that preserves review clarity.
  - Run focused regression tests, npm run release:validate, npm run lint, npm test, logics-manager lint --require-status, and final git status/diff checks before push.
  - Push the named branch, identify the CI run for that exact branch commit, wait for a successful conclusion, then create a PR against main with a concise change and validation summary.
- Out:
  - Committing, pushing, or modifying unrelated user changes found in the working tree.
  - Tagging, publishing npm or PyPI packages, uploading release assets, or creating a hosted release.
  - Merging, approving, or auto-merging the PR.
  - Bypassing failed CI, required checks, protected-branch policy, or version validation.

# Acceptance criteria
- AC1: The task records the exact base SHA, branch name, remote, and selected files before branch creation and commit.
- AC2: The implementation commit contains the Claude-only environment change, regression tests, README adjustment, and their linked Logics records, with no unrelated diff.
- AC3: The release-preparation commit uses the selected semver version consistently in package.json, pyproject.toml, VERSION, CLI-reported version, README badge, and the repository's release note surface.
- AC4: `npm run release:validate`, `npm run lint`, `npm test`, and `logics-manager lint --require-status` all pass on the exact commit that will be pushed.
- AC5: The pushed branch's CI run for that commit completes with success; a failed, cancelled, stale, or branch-mismatched run blocks PR creation.
- AC6: The created PR targets main, links the delivery task where appropriate, states that Claude title writes are disabled only for cdx-managed sessions, and includes the passed validation commands.
- AC7: No tag, release, package publication, checksum upload, merge, or approval is performed by this task.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: The task records the exact base SHA, branch name, remote, and selected files before branch creation and commit.
- request-AC2 -> This backlog slice. Proof: AC2: The implementation commit contains the Claude-only environment change, regression tests, README adjustment, and their linked Logics records, with no unrelated diff.
- request-AC3 -> This backlog slice. Proof: AC3: The release-preparation commit uses the selected semver version consistently in package.json, pyproject.toml, VERSION, CLI-reported version, README badge, and the repository's release note surface.
- request-AC4 -> This backlog slice. Proof: AC4: `npm run release:validate`, `npm run lint`, `npm test`, and `logics-manager lint --require-status` all pass on the exact commit that will be pushed.
- request-AC5 -> This backlog slice. Proof: AC5: The pushed branch's CI run for that commit completes with success; a failed, cancelled, stale, or branch-mismatched run blocks PR creation.
- request-AC6 -> This backlog slice. Proof: AC6: The created PR targets main, links the delivery task where appropriate, states that Claude title writes are disabled only for cdx-managed sessions, and includes the passed validation commands.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_042_reviewable_release_preparation_for_stable_claude_titles`
- Architecture decision(s): (none yet)
- Request: `req_055_land_and_release_the_stable_claude_terminal_title_change`
- Primary task(s): `task_066_create_a_validated_branch_and_pr_for_the_claude_title_release`
- Superseded by: `item_107_disable_claude_s_competing_terminal_title_writes_for_cdx_sessions`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
