## item_066_pass_unvalidated_provider_arguments_through_instead_of_mapping_every_flag - Pass unvalidated provider arguments through instead of mapping every flag
> From version: 0.14.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Provider surface
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-08

# Problem
- Both provider CLIs ship flags faster than cdx can map them: `--add-dir`, `--search`, `--image`, `--allowedTools`, `--sandbox`, `--approve-for-me`, `--profile` and `--agents` are all unmapped today, and the list grows every release.
- There is no escape hatch, so a user who needs any unmapped flag must abandon cdx and lose the account isolation that is the reason to use it.
- Adding these one at a time is a treadmill with no end state, and each addition enlarges a validated surface cdx then has to keep true.

# Preparation findings
- cdx already executes providers through argv lists, never through a shell: every spec in `src/provider_runtime.py` is `{"command": ..., "args": [...]}`. The shell-metacharacter criterion is therefore about *preserving* that property while parsing a user-supplied string into argv, not about adding escaping.
- Splitting the stored string into argv is the one real decision. `shlex.split` gives POSIX quoting semantics and would behave differently on Windows, which CI covers (`ci.yml` runs `windows-latest`). Choose deliberately and state the choice, rather than inheriting it.
- The insertion order matters for precedence: providers generally let the last occurrence of a flag win, so appending passthrough after cdx's mapped arguments makes the user's value take effect. That is a defensible default, but it silently overrides `cdx set`, which is why the collision behaviour has to be observable rather than implicit.
- Three specs would need the passthrough independently - interactive (`:486`), resume (`:598`), headless (`:654`). Deciding whether passthrough applies to all three or to the headless path alone is a scoping question to settle before implementation, not during.
- The exclusions have concrete homes: `cdx schema --json` is built in `src/commands/runs.py`, and `--check-provider-flags` lives in the doctor path. Both must be changed in the same commit that introduces the feature, not after.

# Scope
- In:
  - Add a per-session `extra_args` launch setting, following the established launch-setting pattern.
  - Add a per-run form so a single `cdx run` can pass provider arguments without changing the stored setting.
  - Append passthrough arguments to the provider command line unmodified, after the arguments cdx itself maps.
  - Document explicitly that passthrough arguments are unvalidated and unsupported, and exclude them from `cdx schema --json` and from `cdx doctor --check-provider-flags`.
  - Define what happens when a passthrough argument collides with one cdx maps itself, and make that behaviour observable rather than silent.
- Out:
  - Validating passthrough arguments or checking them against the installed provider CLI.
  - Retiring any currently-mapped setting in favour of passthrough.
  - Any change to the ollama provider.

# Acceptance criteria
- AC1: `cdx set <name> --extra-args "..."` persists, displays in `cdx configs`, and clears through `cdx unset`.
- AC2: Stored passthrough arguments appear on the provider command line unmodified, after cdx's own mapped arguments.
- AC3: A per-run passthrough form reaches the provider without modifying the stored setting.
- AC4: `cdx schema --json` does not describe passthrough arguments, and says that it does not.
- AC5: `cdx doctor --check-provider-flags` neither verifies nor reports passthrough arguments.
- AC6: A passthrough argument that duplicates one cdx maps produces the documented, observable outcome rather than a silent surprise.
- AC7: Arguments containing shell metacharacters are passed as literal argv entries and never through a shell.

# AC Traceability
- request-AC9 -> This backlog slice. Proof: AC1: `cdx set <name> --extra-args "..."` persists, displays in `cdx configs`, and clears through `cdx unset`.
- request-AC10 -> This backlog slice. Proof: AC2: Stored passthrough arguments appear on the provider command line unmodified, after cdx's own mapped arguments.
- request-AC13 -> This backlog slice. Proof: AC3: A per-run passthrough form reaches the provider without modifying the stored setting.
- request-AC4 -> This backlog slice. Evidence needed: cdx records a provider-native session identifier, and its provenance, for each session that supports one - imposed for Claude through `--session-id`, observed for Codex by reading the rollout's `session_id` after a run - and `cdx resume <name>` uses that identifier instead of the recency heuristics `codex resume --last` and `claude --continue`, so resuming is unaffected by the working directory or by other sessions having run more recently.
- request-AC5 -> This backlog slice. Evidence needed: `cdx can-resume <name> --json` reports which resume strategy will actually be used (identity-based or recency-based) and why, so a caller can tell a reliable resume from a best-effort one before relying on it.
- request-AC6 -> This backlog slice. Evidence needed: `cdx run --failover` detects that a run has terminated because of a provider rate limit, distinguishes that cause from every other failure, corroborates it against the account's own refreshed status before acting, re-ranks the remaining sessions, transfers the working context, and continues the task on the next eligible session without user intervention; every ambiguous case is biased towards not failing over, because a false positive migrates a healthy run off a working account.
- request-AC7 -> This backlog slice. Evidence needed: A run that failed over is fully traceable: `cdx run-report <run_id> --json` names every session the run occupied, in order, with the reason for each transition, and `cdx runs` shows the run as one run rather than as several unrelated ones.
- request-AC8 -> This backlog slice. Evidence needed: When no eligible session remains, a failover run terminates with a specific error code that distinguishes 'exhausted every account' from 'the task itself failed', and reports what was attempted.
- request-AC11 -> This backlog slice. Evidence needed: Where the installed provider CLI offers native background execution, `cdx run --detach` delegates to it rather than to the in-house detached launcher, decided by capability detection against the installed CLI rather than by a version assumption.
- request-AC12 -> This backlog slice. Evidence needed: When the installed CLI offers no native background execution, the existing in-house detached path continues to work exactly as it does today, and which path was taken is visible in the run record.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_018_executable_quota_routing`
- Architecture decision(s): (none yet)
- Request: `req_028_turn_quota_awareness_from_advice_into_execution_across_accounts_and_providers`
- Primary task(s): `task_039_orchestrate_executable_quota_routing_across_accounts_and_providers`

# AI Context
- Summary: Pass unvalidated provider arguments through instead of mapping every flag
- Keywords: scaffolded-backlog, pass unvalidated provider arguments through instead of mapping every flag, implementation-ready
- Use when: Implementing the scaffolded slice for Pass unvalidated provider arguments through instead of mapping every flag.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_039_orchestrate_executable_quota_routing_across_accounts_and_providers`

# Notes
- Task `task_039_orchestrate_executable_quota_routing_across_accounts_and_providers` was finished via `logics-manager flow finish task` on 2026-08-08.
