## item_064_anchor_resume_and_handoff_on_a_provider_native_session_identity - Anchor resume and handoff on a provider-native session identity
> From version: 0.14.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 20%
> Complexity: Medium
> Theme: Session identity
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-08

# Problem
- `get_resume_capability` at `src/provider_runtime.py:555` resolves resume to `codex resume --last --cd <cwd>` and `claude --continue`, both of which mean 'the most recent conversation in this directory'. Resuming therefore depends on the working directory and on no other session having run since.
- `handoff` reconstructs context by scraping the source session's terminal transcript. It is the only cross-provider transfer that exists and it works, but a terminal transcript is a weak anchor for anything that must run unattended.
- Claude's `--session-id <uuid>` and `--fork-session`, and Codex's `resume <id>` and `fork`, make identity-based resume available for the first time. Without adopting them, the failover this request builds would be founded on transcript scraping.

# Preparation findings
The two providers reach session identity from opposite directions. This is the
central design fact of the slice and it was not visible when the request was
written.

- **Claude lets cdx impose the identity.** `--session-id <uuid>` takes a caller-supplied UUID ("must be a valid UUID"), and `-r/--resume [value]` resumes by that session ID. cdx can therefore generate the UUID itself, store it on the session record before launching, and resume deterministically. The identity is known *before* the first launch.
- **Codex only lets cdx discover it.** No flag imposes a session id. `codex resume [SESSION_ID]` accepts "Session id (UUID) or session name. UUIDs take precedence if it parses." The id must be read back after the run.
- Discovery for Codex is already within reach: each rollout file's first line is a session-meta record carrying `payload.session_id`, and the filename embeds the same UUID (`rollout-<timestamp>-<uuid>.jsonl`). Verified against a real rollout under the global Codex home. `find_latest_status_artifact` in `src/status_source.py` already walks exactly these paths for status resolution, so the traversal exists and needs a second reader rather than a new one.
- Consequence for the design: the recorded identifier has two provenances - *imposed* (Claude, known pre-launch, always available) and *observed* (Codex, known post-launch, absent until the session has run at least once). `cdx can-resume` must be able to say which, because an observed identity can legitimately be missing while an imposed one cannot.
- `_build_resume_spec` already passes `--name session["name"]` for Claude, so cdx is halfway to naming Claude sessions; `--session-id` is the identity-grade version of that.
- Codex also exposes `archive`, `unarchive` and `delete` "by id or session name", which is why session names are a real Codex concept - but nothing found in `codex --help` or `codex exec --help` sets that name at launch, so names are not a usable anchor for cdx.

# Scope
- In:
  - Record a provider-native session identifier on the session record, with its provenance (`imposed` for Claude, `observed` for Codex), for Codex and Claude only.
  - For Claude: generate a UUID per session, persist it, and pass it as `--session-id` on launch, so the identity exists before the first run.
  - For Codex: after a run, read the session id back from the newest rollout under the session's `CODEX_HOME` (`payload.session_id` on the session-meta line, mirrored in the filename), reusing the traversal `find_latest_status_artifact` already performs in `src/status_source.py`.
  - Extend `get_resume_capability` (`src/provider_runtime.py:555`) to report an identity-based strategy when an identifier is recorded, keeping the current recency strategy as the fallback.
  - Use the identifier in `_build_resume_spec` (`src/provider_runtime.py:583`) in place of `claude --continue` and `codex resume --last` when it is available.
  - Report the strategy actually chosen, its provenance, and the reason, through `cdx can-resume --json`.
  - Use the identifier as the anchor for `handoff` where one exists, keeping transcript scraping for sessions that have none.
- Out:
  - Forking sessions (`--fork-session`, `codex fork`), which is a separate capability once identity exists.
  - Codex `archive`/`unarchive`/`delete` session management.
  - Removing transcript scraping, which remains the fallback for sessions without an identifier.
  - Any change to the ollama provider.

# Acceptance criteria
- AC1: A Claude session carries a valid UUID identifier from the moment it is registered, before it has ever been launched, and that UUID is passed as `--session-id` on launch.
- AC2: A Codex session carries no identifier until it has run once, and carries the rollout's `session_id` afterwards.
- AC3: The session record states the provenance of the identifier, distinguishing imposed from observed.
- AC4: `cdx resume <name>` for a session with a recorded identifier resumes that exact conversation, and does so from a different working directory than the one it was launched in.
- AC5: `cdx resume <name>` still succeeds through the existing recency path for a session with no recorded identifier, which for Codex includes every session that has never run.
- AC6: `cdx can-resume <name> --json` names the strategy that will be used, distinguishes identity-based from recency-based, and reports the provenance.
- AC7: Launching an unrelated session in between does not change which conversation `cdx resume <name>` resumes.
- AC8: `handoff` uses the recorded identifier where one exists and falls back to transcript scraping where none does, with the source reported in its JSON payload.
- AC9: A rollout that is unreadable, truncated, or missing its session-meta line leaves the session on the recency path rather than recording a malformed identifier.

# AC Traceability
- request-AC4 -> This backlog slice. Proof: AC1, AC2 and AC3 record the identifier and its provenance for each provider; AC4 and AC7 show resume following the identifier rather than recency.
- request-AC5 -> This backlog slice. Proof: AC6: `cdx can-resume <name> --json` names the strategy, distinguishes identity-based from recency-based, and reports the provenance.
- request-AC13 -> This backlog slice. Proof: the ollama provider is listed out of scope, and identity is recorded for Codex and Claude only.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_018_executable_quota_routing`
- Architecture decision(s): (none yet)
- Request: `req_028_turn_quota_awareness_from_advice_into_execution_across_accounts_and_providers`
- Primary task(s): `task_039_orchestrate_executable_quota_routing_across_accounts_and_providers`

# AI Context
- Summary: Anchor resume and handoff on a provider-native session identity
- Keywords: scaffolded-backlog, anchor resume and handoff on a provider-native session identity, implementation-ready
- Use when: Implementing the scaffolded slice for Anchor resume and handoff on a provider-native session identity.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
