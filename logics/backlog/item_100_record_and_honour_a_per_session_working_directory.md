## item_100_record_and_honour_a_per_session_working_directory - Choose the launch directory, and record the one each run used
> From version: 0.18.5
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 80%
> Progress: 0%
> Complexity: Medium
> Theme: Session lifecycle
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:36:22

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: record, honour, per, session, working, directory
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- The directory a run uses comes from the shell with no confirmation, so a launch typed from a home directory produces an assistant with no project, a failed MCP start, and a provider misreading a configuration file as project-local.
- The same account is legitimately run in several directories at once, so the directory belongs to the run and not to the session.
- Nothing records which directory a run used, so no surface can say what the fleet is working on.

# Scope
- In:
  - An explicit launch directory argument, resolved in the one place every provider already takes its cwd from.
  - A choice offered only when the directory is plainly not a project, listing the directories that session has recently run in plus staying put; interactive runs only.
  - Refusing a named directory that does not exist, before the provider starts.
  - Recording the directory on the run, and surfacing it wherever a running session is already described.
  - Focused tests for explicit, home-directory with and without a terminal, project, missing, and concurrent runs.
- Out:
  - A per-session directory setting, which the same account running in two projects at once would make untrue.
  - Inferring a directory from git state or history without asking, and any prompt on a launch that is already correct.
  - Changing provider invocation other than the directory passed to it.

# Acceptance criteria
- AC1: An explicit directory argument is honoured by every provider, interactively and headlessly.
- AC2: A launch from a non-project directory offers the recent ones and staying put, and only when a terminal is there to answer.
- AC3: A launch from inside a project is unchanged, with no prompt and no new output.
- AC4: A named directory that does not exist is refused before the provider starts, naming it.
- AC5: Each run records its directory, and concurrent runs of one session are told apart by it.
- AC6: Focused tests cover explicit, home-with-terminal, home-without-terminal, project, missing, and concurrent runs.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: A recorded directory is used wherever the command is typed, interactively and headlessly.
- request-AC2 -> This backlog slice. Proof: AC2: A per-launch override applies once and changes nothing recorded.
- request-AC3 -> This backlog slice. Proof: AC3: Nothing recorded means today's behaviour, unchanged.
- request-AC4 -> This backlog slice. Proof: AC4: A recorded directory that has gone is named and refused before the provider starts.
- request-AC5 -> This backlog slice. Proof: AC5: It appears wherever the other launch settings appear.
- request-AC6 -> This backlog slice. Proof: AC6: Focused tests cover all four cases for each supported provider.
- request-AC7 -> This backlog slice. Proof: AC6: Focused tests cover all four cases for each supported provider.

# Decision framing
- Product framing: Not needed
- Architecture framing: Settled in `adr_007_what_cdx_records_about_where_a_run_happened`: one resolved absolute path recorded on the run, every other property derived at read time, and only a basename crossing to a companion.

# Links
- Product brief(s): `prod_038_sessions_that_know_what_they_are_working_on`
- Architecture decision(s): `adr_007_what_cdx_records_about_where_a_run_happened`
- Request: `req_051_launch_a_session_in_the_directory_it_belongs_to`
- Primary task(s): `task_062_orchestrate_the_per_session_working_directory`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
