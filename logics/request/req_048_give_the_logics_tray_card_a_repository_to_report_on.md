## req_048_give_the_logics_tray_card_a_repository_to_report_on - Give the Logics tray card a repository to report on
> From version: 0.18.5
> Schema version: 1.0
> Status: Draft
> Understanding: 85%
> Confidence: 75%
> Complexity: Low
> Theme: Tray usability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:36:23

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: logics, tray, card, repository, report
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Needs
- The Logics card is built by running logics-manager in the working directory of whatever asked for the snapshot. The tray companion is started at login and has no meaningful working directory, so the card it was built for is absent in exactly the situation it exists for — enabled, installed, and silent.
- Naming a repository by hand answers that, and answers it badly: an operator running several sessions is working in several repositories at once, and a single named path would report on one of them and quietly ignore the rest.
- Measured after release: `cdx tray status` reports the card from inside a Logics repository and reports nothing from a home directory or from `/`. Every test injected the status JSON, so none of them ever exercised the directory the command runs in.

# Context
- req_037 specifies the card as absent when Logics is unavailable, which is the right degradation for an absent tool. This is a different cause with the same symptom: the tool is installed and the repository is elsewhere.
- cdx view already faces the same question and answers it by running where the user is, which a companion cannot do.
- CDX knows the answer without asking: it launched each session in a directory, so the repositories in play are the ones its own sessions are working in. That is more reliable than a preference nobody remembers to update, and it covers several repositories rather than one.
- The alert envelope is deliberately not the source. It carries `project` as a basename, not a path, because `task_050` put transcript paths and provider identifiers outside the boundary and a full working directory is closer to those than to a session name. A session's own directory is CDX's data about its own launch, so taking it there avoids the question rather than arguing about it.
- Several repositories means the card has to say which one each row belongs to, or say nothing useful. That is the part worth designing before implementing.
- `req_051` is what makes the derivation possible at all: it records the directory each run actually used, which is the only place that fact exists. A per-session setting was considered and rejected there — the same account legitimately runs in two projects at once — so what this card reads is the set of directories the *running* sessions are in, which is also the honest answer to "several at once".
- Whatever carries the answer has to survive `cdx tray install`, `cdx update`, and a companion restart, so it belongs with the other durable tray preferences in CDX rather than in the adapter.

# Acceptance criteria
- AC1: The card reports on the repositories CDX's own enabled sessions are working in, without anything being named by hand.
- AC2: The card is identical whatever directory the snapshot was requested from, including a companion started at login with no meaningful one.
- AC3: A session directory that has disappeared, or is not a Logics repository, contributes nothing and raises no error — exactly as an absent logics-manager does today.
- AC4: When more than one repository is in play, each row says which one it belongs to; the card never merges two repositories into counts that describe neither.
- AC5: No session working directory leaves CDX in an alert payload or the tray spool; what the card carries is what a menu row needs to name a repository, and nothing more.
- AC6: An operator can still override the derived answer explicitly, for the case where the repository they care about has no session open in it.
- AC7: Focused tests cover one repository, several, none, a directory that is not a Logics repository, and the explicit override; project validation passes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_035_a_logics_card_that_knows_which_repository_it_is_about`
- Architecture decision(s): `adr_007_what_cdx_records_about_where_a_run_happened`

# References
- src/tray_logics.py
- src/tray_plugins.py
- src/commands/tray.py

# Backlog
- `item_096_name_the_repository_the_logics_card_reports_on`
