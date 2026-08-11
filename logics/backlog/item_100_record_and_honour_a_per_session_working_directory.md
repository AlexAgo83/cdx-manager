## item_100_record_and_honour_a_per_session_working_directory - Record and honour a per-session working directory
> From version: 0.18.5
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Session lifecycle
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: record, honour, per, session, working, directory
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- The directory a session runs in comes from the shell, so the same session is a different session depending on where it was typed.
- A launch from a home directory produces an assistant with no project, a failed MCP start, and a provider misreading a configuration file as project-local.

# Scope
- In:
  - A per-session working directory, set and cleared like the other launch settings.
  - Using it at interactive and headless launch, with a per-launch override.
  - Refusing before the provider starts when the recorded directory is gone, naming it.
  - Showing it in the configuration view and the JSON session surfaces.
  - Focused tests per provider for recorded, overridden, absent and missing.
- Out:
  - Inferring a directory, managing git state, or per-session environment beyond the directory.
  - Changing provider invocation other than the directory passed to it.

# Acceptance criteria
- AC1: A recorded directory is used wherever the command is typed, interactively and headlessly.
- AC2: A per-launch override applies once and changes nothing recorded.
- AC3: Nothing recorded means today's behaviour, unchanged.
- AC4: A recorded directory that has gone is named and refused before the provider starts.
- AC5: It appears wherever the other launch settings appear.
- AC6: Focused tests cover all four cases for each supported provider.

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
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_038_sessions_that_know_what_they_are_working_on`
- Architecture decision(s): (none yet)
- Request: `req_051_launch_a_session_in_the_directory_it_belongs_to`
- Primary task(s): `task_062_orchestrate_the_per_session_working_directory`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
