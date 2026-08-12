## req_055_land_and_release_the_stable_claude_terminal_title_change - Land and release the stable Claude terminal-title change
> From version: 0.18.6
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: release-delivery
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: land, release, stable, claude, terminal, title, change
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Needs
- Move the completed Claude terminal-title fix off main into a reviewable feature branch without losing the existing uncommitted implementation or its linked Logics corpus.
- Prepare a consistent next release version and release notes for the user-visible fix.
- Push only a clean, validated branch, wait for the branch CI conclusion, and create a pull request only when CI is successful.

# Context
- The implementation uses Claude Code's `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` environment variable so cdx retains `session — folder` while Claude is busy, rather than racing title updates.
- The repository version is duplicated in package.json, pyproject.toml, VERSION, the CLI-reported version, and the README version badge; release validation checks their alignment.
- The checksum ledger intentionally has no required entry for an unreleased working-tree version, while an explicit released tag must have archive metadata.
- Branch creation, commits, remote push, version selection, and PR creation alter shared history or external state and must be performed only in the delivery task after verifying the exact targets and gates.

# Acceptance criteria
- AC1: A new feature branch rooted at the verified main commit contains the existing implementation and its Logics documentation, with unrelated work excluded.
- AC2: The implementation commit is reviewable, uses the project conventions, and records no unvalidated or unintended files.
- AC3: The selected next semantic version is deliberate, consistent across every required source, documented in release notes, and passes `npm run release:validate`.
- AC4: Before push, the branch passes the relevant focused tests, full lint, full test suite, Logics lint, and a final diff/status review.
- AC5: The branch is pushed to the intended remote only after local gates pass; the matching CI run completes successfully before a PR is created.
- AC6: The PR targets the intended base branch, describes the Claude-specific terminal-title fix and validation evidence, and excludes release publication or tagging.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_042_reviewable_release_preparation_for_stable_claude_titles`
- Architecture decision(s): (none yet)

# References
- Current working tree contains the completed Claude terminal-title implementation in src/provider_runtime.py, README.md, and test/test_runtime_py.py.
- Current branch is main at 6a85c27; the latest release tag is v0.18.6 and package.json plus pyproject.toml declare 0.18.6.
- package.json defines npm run lint, npm test, and npm run release:validate; .github/workflows/ci.yml runs lint and tests on Ubuntu and Windows.
- User delivery sequence: create a new branch, commit the completed change, prepare the release version before the release commit and push, then open a PR only after CI passes.

# Backlog
- `item_108_prepare_the_claude_terminal_title_fix_for_a_gated_pull_request`
