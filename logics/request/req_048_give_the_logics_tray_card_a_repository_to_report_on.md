## req_048_give_the_logics_tray_card_a_repository_to_report_on - Give the Logics tray card a repository to report on
> From version: 0.18.5
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Low
> Theme: Tray usability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: logics, tray, card, repository, report
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Needs
- The Logics card is built by running logics-manager in the working directory of whatever asked for the snapshot. The tray companion is started at login and has no meaningful working directory, so the card it was built for is absent in exactly the situation it exists for — enabled, installed, and silent.
- Measured after release: `cdx tray status` reports the card from inside a Logics repository and reports nothing from a home directory or from `/`. Every test injected the status JSON, so none of them ever exercised the directory the command runs in.

# Context
- req_037 specifies the card as absent when Logics is unavailable, which is the right degradation for an absent tool. This is a different cause with the same symptom: the tool is installed and the repository is elsewhere.
- cdx view already faces the same question and answers it by running where the user is, which a companion cannot do.
- Whatever carries the answer has to survive `cdx tray install`, `cdx update`, and a companion restart, so it belongs with the other durable tray preferences in CDX rather than in the adapter.

# Acceptance criteria
- AC1: An operator can name the repository the Logics card reports on, and can clear it.
- AC2: The card is built against that repository whatever directory the snapshot was requested from, including a companion started at login.
- AC3: A named repository that has disappeared or is not a Logics repository produces no card and no error, exactly as an absent logics-manager does today.
- AC4: Nothing is reported implicitly: with no repository named, the behaviour is what it is today rather than a guess at which project was meant.
- AC5: Focused tests cover the named repository, the missing one, and the unset one; project validation passes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_035_a_logics_card_that_knows_which_repository_it_is_about`
- Architecture decision(s): (none yet)

# References
- src/tray_logics.py
- src/tray_plugins.py
- src/commands/tray.py

# Backlog
- `item_096_name_the_repository_the_logics_card_reports_on`
