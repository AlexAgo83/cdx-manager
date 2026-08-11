## item_096_name_the_repository_the_logics_card_reports_on - Name the repository the Logics card reports on
> From version: 0.18.5
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Tray usability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: name, repository, logics, card, reports
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- The adapter runs logics-manager in the caller's working directory, and the caller is a companion with none.
- The card is therefore absent in normal use while appearing correct in every test and in every hand-run check from a project directory.

# Scope
- In:
  - A CDX-side setting for the repository path, set and cleared explicitly.
  - Running the adapter against that path rather than the caller's directory.
  - Falling back to silence when the path is gone or is not a Logics repository.
- Out:
  - Automatic discovery, multiple repositories, or per-session repositories.
  - Changes to the card's contents, bounds, refresh cadence or action vocabulary.

# Acceptance criteria
- AC1: The repository is named through CDX, reversibly, and stored with the other tray preferences.
- AC2: The card is identical whether the snapshot is requested from that repository, from a home directory, or from /.
- AC3: A path that is gone, or is not a Logics repository, yields no card and no error.
- AC4: With nothing named, behaviour is unchanged from today.
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
