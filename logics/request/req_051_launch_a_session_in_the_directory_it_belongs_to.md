## req_051_launch_a_session_in_the_directory_it_belongs_to - Launch a session in the directory it belongs to
> From version: 0.18.5
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Session lifecycle
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: launch, session, directory, belongs
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Needs
- `cdx <name>` launches wherever the shell happens to be. Run it from a home directory and the assistant opens on that home directory: no project, an MCP server that cannot start because there is nothing for it to serve, and a provider reading the wrong file as a project-local config. Observed on a real launch, and the assistant was one prompt away from working on nothing.
- The directory is not an incidental property of a launch. A session is an account working on something, and which something is stable — far more stable than which terminal tab the operator happened to be in when they typed the name.
- Correcting it afterwards costs a quit and a relaunch, by which point the provider has already read its configuration and started its servers.

# Context
- cdx already passes the current directory to the provider — Codex receives `--cd` — so the mechanism exists and only its source is wrong.
- Every other durable launch decision is already a per-session setting: provider, permission, model, reasoning effort, alerts. A working directory is the one that decides what the session is about, and it is the one that is not recorded.
- There is a second payoff, and it is not incidental: req_048 needs to know which repositories CDX's sessions are working in, and today it can only ask where the process happens to be. A recorded directory answers both questions with one fact.
- Overriding at launch has to stay possible. Someone opening a session on a different tree for one task should not have to change a setting and change it back.

# Acceptance criteria
- AC1: A session can record the directory it belongs to, and launches there whatever directory the command was typed in.
- AC2: A launch can override it explicitly for that launch alone, without changing what was recorded.
- AC3: A session with nothing recorded behaves exactly as it does today, launching where the command was run.
- AC4: A recorded directory that no longer exists is reported before the provider starts, rather than launching somewhere unintended.
- AC5: The recorded directory appears in the session's configuration view alongside the other launch settings, and in the JSON surfaces that already describe a session.
- AC6: Headless runs honour the same rule, so a scripted run and an interactive one work on the same tree.
- AC7: Focused tests cover recorded, overridden, absent, and missing-directory launches for each supported provider; project validation passes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_038_sessions_that_know_what_they_are_working_on`
- Architecture decision(s): (none yet)

# References
- src/provider_runtime.py
- src/session_service.py
- src/commands/settings.py
- req_048_give_the_logics_tray_card_a_repository_to_report_on

# Backlog
- `item_100_record_and_honour_a_per_session_working_directory`
