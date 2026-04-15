## task_003_multi_provider_session_support_for_codex_and_claude - multi-provider session support for Codex and Claude
> From version: 1.13.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: High
> Theme: CLI
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Derived from backlog item `item_002_multi_provider_session_support_for_codex_and_claude`.
- Source file: `logics/backlog/item_002_multi_provider_session_support_for_codex_and_claude.md`.
- The product should support more than one assistant provider without forcing a redesign of the session model.

```mermaid
%% logics-kind: task
%% logics-signature: task|multi-provider-session-support-for-codex|item-002-multi-provider-session-support-|1-confirm-scope-dependencies-and-linked|run-the-relevant-automated-tests-for
stateDiagram-v2
    state "item_002_multi_provider_session_support_fo" as Backlog
    state "1. Confirm scope dependencies and linked" as Scope
    state "2. Implement the next coherent delivery" as Build
    state "3. Checkpoint the wave in a" as Verify
    state "Run the relevant automated tests for" as Validation
    state "Done report" as Report
    [*] --> Backlog
    Backlog --> Scope
    Scope --> Build
    Build --> Verify
    Verify --> Validation
    Validation --> Report
    Report --> [*]
```

# Plan
- [ ] 1. Confirm scope, dependencies, and linked acceptance criteria.
- [ ] 2. Implement the next coherent delivery wave from the backlog item.
- [ ] 3. Checkpoint the wave in a commit-ready state, validate it, and update the linked Logics docs.
- [ ] CHECKPOINT: leave the current wave commit-ready and update the linked Logics docs before continuing.
- [ ] CHECKPOINT: if the shared AI runtime is active and healthy, run `python logics/skills/logics.py flow assist commit-all` for the current step, item, or wave commit checkpoint.
- [ ] GATE: do not close a wave or step until the relevant automated tests and quality checks have been run successfully.
- [ ] FINAL: Update related Logics docs

# Delivery checkpoints
- Each completed wave should leave the repository in a coherent, commit-ready state.
- Update the linked Logics docs during the wave that changes the behavior, not only at final closure.
- Prefer a reviewed commit checkpoint at the end of each meaningful wave instead of accumulating several undocumented partial states.
- If the shared AI runtime is active and healthy, use `python logics/skills/logics.py flow assist commit-all` to prepare the commit checkpoint for each meaningful step, item, or wave.
- Do not mark a wave or step complete until the relevant automated tests and quality checks have been run successfully.

# AC Traceability
- AC1 -> Scope: A session can be created with an explicit provider value for Codex or Claude using the documented syntax.. Proof: capture validation evidence in this doc.
- AC2 -> Scope: Starting a session routes to the matching provider.. Proof: capture validation evidence in this doc.
- AC3 -> Scope: Session listings show which provider each session belongs to.. Proof: capture validation evidence in this doc.
- AC4 -> Scope: Unsupported provider values fail with a clear error message.. Proof: capture validation evidence in this doc.
- AC5 -> Scope: Existing Codex-only usage keeps working without requiring a new mental model.. Proof: capture validation evidence in this doc.

# Decision framing
- Product framing: Not needed
- Product signals: (none detected)
- Product follow-up: No product brief follow-up is expected based on current signals.
- Architecture framing: Required
- Architecture signals: data model and persistence, contracts and integration
- Architecture follow-up: Create or link an architecture decision before irreversible implementation work starts.

# Links
- Product brief(s): `prod_000_codex_multi_account_session_manager`
- Architecture decision(s): (none yet)
- Derived from `item_002_multi_provider_session_support_for_codex_and_claude`
- Request(s): `req_XXX_example`

# AI Context
- Summary: Extend session handling so named sessions can target Codex or Claude explicitly.
- Keywords: provider, Codex, Claude, session, routing, list output
- Use when: Use when implementing provider-aware session creation, launch, or display.
- Skip when: Skip when the change only concerns persistence or command ergonomics.
# Validation
- Run the relevant automated tests for the changed surface before closing the current wave or step.
- Run the relevant lint or quality checks before closing the current wave or step.
- Confirm the completed wave leaves the repository in a commit-ready state.

# Definition of Done (DoD)
- [ ] Scope implemented and acceptance criteria covered.
- [ ] Validation commands executed and results captured.
- [ ] No wave or step was closed before the relevant automated tests and quality checks passed.
- [ ] Linked request/backlog/task docs updated during completed waves and at closure.
- [ ] Each completed wave left a commit-ready checkpoint or an explicit exception is documented.
- [ ] Status is `Done` and progress is `100%`.

# Report
