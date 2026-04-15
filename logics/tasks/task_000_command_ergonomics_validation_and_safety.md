## task_000_command_ergonomics_validation_and_safety - command ergonomics validation and safety
> From version: 1.13.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: CLI
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Derived from backlog item `item_003_command_ergonomics_validation_and_safety`.
- Source file: `logics/backlog/item_003_command_ergonomics_validation_and_safety.md`.
- A terminal tool becomes frustrating if the commands are hard to discover, ambiguous, or unsafe to use by mistake.

```mermaid
%% logics-kind: task
%% logics-signature: task|command-ergonomics-validation-and-safety|item-003-command-ergonomics-validation-a|1-confirm-scope-dependencies-and-linked|run-the-relevant-automated-tests-for
stateDiagram-v2
    state "item_003_command_ergonomics_validation_and" as Backlog
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
- AC1 -> Scope: `cdx` and `cdx --help` explain the available commands in a concise way.. Proof: capture validation evidence in this doc.
- AC2 -> Scope: Invalid syntax returns a readable usage hint instead of a stack trace.. Proof: capture validation evidence in this doc.
- AC3 -> Scope: Duplicate names, unknown names, and invalid provider values produce clear errors.. Proof: capture validation evidence in this doc.
- AC4 -> Scope: Removing a session is intentionally safe, either with confirmation or an explicit force flag.. Proof: capture validation evidence in this doc.
- AC5 -> Scope: List output is readable enough to be used as the default discovery surface.. Proof: capture validation evidence in this doc.
- AC6 -> Scope: `cdx --version` and `cdx -v` print the installed version and exit without side effects.. Proof: capture validation evidence in this doc.
- AC7 -> Scope: `cdx -h` is accepted as an alias for `cdx --help`.. Proof: capture validation evidence in this doc.

# Decision framing
- Product framing: Consider
- Product signals: navigation and discoverability
- Product follow-up: Review whether a product brief is needed before scope becomes harder to change.
- Architecture framing: Required
- Architecture signals: data model and persistence, contracts and integration
- Architecture follow-up: Create or link an architecture decision before irreversible implementation work starts.

# Links
- Product brief(s): `prod_000_codex_multi_account_session_manager`
- Architecture decision(s): (none yet)
- Derived from `item_003_command_ergonomics_validation_and_safety`
- Request(s): `req_XXX_example`

# AI Context
- Summary: Improve command help, validation, and safety for the cdx CLI surface.
- Keywords: help, usage, validation, safety, delete, version, error handling, alias flags
- Use when: Use when shaping the user-facing command experience.
- Skip when: Skip when the change is only about storage or provider routing.
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
