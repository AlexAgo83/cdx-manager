## item_096_name_the_repository_the_logics_card_reports_on - Name the repository the Logics card reports on
> From version: 0.18.5
> Schema version: 1.0
> Status: In progress
> Understanding: 85%
> Confidence: 75%
> Progress: 90%
> Complexity: Low
> Theme: Tray usability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:38:55

# AI Context
- Summary: Derive the card's repositories from the directories the running sessions recorded, and name the repository per row when several are in play.
- Keywords: Logics card, running sessions, derived repository, adr_007
- Use when: Implementing the card's repository resolution once req_051 records run directories.
- Skip when: Changing what the card shows per repository, or adding new Logics capabilities.

# Problem
- The adapter runs logics-manager in the caller's working directory, and the caller is a companion with none.
- An operator with several sessions is working in several repositories at once, so a single named path would report on one and ignore the rest.
- The card is therefore absent in normal use while appearing correct in every test and in every hand-run check from a project directory.

# Scope
- In:
  - Derive the repositories from the working directories of CDX's own enabled sessions, which it already knows because it launched them.
  - Run the adapter against each, and name the repository on every row when more than one is in play.
  - Keep an explicit override for a repository with no session open in it.
  - Fall back to silence for a directory that is gone or is not a Logics repository.
- Out:
  - Scanning the filesystem for repositories, or reporting on any directory no session is working in and nobody named.
  - Changes to the card's contents, bounds, refresh cadence or action vocabulary.

# Acceptance criteria
- AC1: The repositories come from the sessions' own directories, with an explicit override available and reversible.
- AC2: The card is identical whether the snapshot is requested from that repository, from a home directory, or from /.
- AC3: A path that is gone, or is not a Logics repository, yields no card and no error.
- AC4: With several repositories in play, each row names its own; counts are never merged across repositories.
- AC5: Focused tests cover all four cases.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: The repository is named through CDX, reversibly, and stored with the other tray preferences.
- request-AC2 -> This backlog slice. Proof: AC2: The card is identical whether the snapshot is requested from that repository, from a home directory, or from /.
- request-AC3 -> This backlog slice. Proof: AC3: A path that is gone, or is not a Logics repository, yields no card and no error.
- request-AC4 -> This backlog slice. Proof: AC4: With nothing named, behaviour is unchanged from today.
- request-AC5 -> This backlog slice. Proof: AC5: Focused tests cover all four cases.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_035_a_logics_card_that_knows_which_repository_it_is_about`
- Architecture decision(s): (none yet)
- Request: `req_048_give_the_logics_tray_card_a_repository_to_report_on`
- Primary task(s): `task_059_orchestrate_the_repository_aware_logics_card`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
