## req_051_launch_a_session_in_the_directory_it_belongs_to - Know and choose where a session is being launched
> From version: 0.18.5
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 80%
> Complexity: Medium
> Theme: Session lifecycle
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:48:32

# AI Context
- Summary: A launch takes its directory from the shell with no confirmation, and nothing records which directory a run used.
- Keywords: working directory, launch, run record, project detection, cwd
- Use when: Deciding how a session picks where it runs, or how CDX reports what its sessions are working on.
- Skip when: Changing what a provider is invoked with beyond its directory, or per-session settings that are properties of the account.

# Needs
- `cdx <name>` launches wherever the shell happens to be. Run it from a home directory and the assistant opens on that home directory: no project, an MCP server that cannot start because there is nothing for it to serve, and a provider reading the wrong file as a project-local config. Observed on a real launch, and the assistant was one prompt away from working on nothing.
- Recording a directory per session is the wrong shape and was the first answer considered. An operator switches between projects all day, and the same account can legitimately be running in two directories at once — so a setting would describe a state that does not exist, and would have to be changed every time it was right.
- Correcting a bad launch afterwards costs a quit and a relaunch, by which point the provider has already read its configuration and started its servers.
- Nothing records where a running session is working. The runtime keeps its pid, its command, its label and its transcript, and not the one fact that says what it is working on — so neither `cdx status`, nor the tray, nor anything else can answer "what are my sessions on right now" for a fleet spread across several projects.

# Context
- cdx already passes the current directory to the provider — Codex receives `--cd` — so the mechanism exists and only its source is wrong.
- The other launch settings — provider, permission, model, effort, alerts — are properties of the account. The directory is a property of *this run*, which is why it belongs with the runtime rather than with the session.
- The friction has to land only where the problem is. Launching from inside a project is the overwhelmingly common case and already correct; it must gain nothing, not a prompt and not a flag to remember.
- req_048 needs to know which repositories are in play. A directory recorded per run answers it for several projects at once, which a per-session setting could not, and it comes from CDX's own record of what it launched rather than from a provider payload.

# Acceptance criteria
- AC1: A launch can name its directory explicitly with `--dir`, and that is the only way a directory is ever chosen for the operator — no per-session setting is introduced.
- AC2: Launching from the home directory or from `/` does not proceed silently: an interactive launch offers the directories that session has recently run in, plus staying where it is. Nowhere else triggers it, so a launch from any working directory is untouched.
- AC3: Launching from inside a project is unchanged: no prompt, no extra flag, no new output.
- AC4: A non-interactive or JSON launch never prompts; it proceeds as today and says which directory it used.
- AC5: A named directory that does not exist is refused before the provider starts, naming it.
- AC6: Every run records the directory it ran in, so several sessions across several projects can each be told apart while running.
- AC7: The recorded directory appears wherever a running session is already described, including `cdx status` and the tray snapshot.
- AC8: Focused tests cover an explicit directory, a home-directory launch with and without a terminal, a project launch, a missing directory, and the recording of several concurrent runs; project validation passes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_038_sessions_that_know_what_they_are_working_on`
- Architecture decision(s): `adr_007_what_cdx_records_about_where_a_run_happened`

# References
- src/provider_runtime.py
- src/session_service.py
- src/commands/settings.py
- req_048_give_the_logics_tray_card_a_repository_to_report_on

# Backlog
- `item_100_record_and_honour_a_per_session_working_directory`
