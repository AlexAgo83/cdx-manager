## item_104_record_which_terminal_a_hook_fired_from_and_carry_it_to_the_tray - Record which terminal a hook fired from, and carry it to the tray
> From version: 0.18.6
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: agent-alerts
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: record, terminal, hook, fired, carry, tray
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- The alert names the session and the project but nothing about where that session is displayed.
- The obvious source is unavailable: a hook has no tty on any descriptor.
- structured_details deliberately enumerates what may cross into the spool, so an addition has to be argued rather than appended.

# Scope
- In:
  - Read the terminal identity from the environment the hook inherited: the terminal program, and the per-session identifier it publishes.
  - Normalise it into named fields through the same text sanitisation every other detail passes.
  - Add those fields to structured_details, documenting them beside the existing statement of what may not cross.
  - Publish them in the alert so the companion receives them, as a minor addition an older companion ignores.
- Out:
  - Any focusing behaviour; this item only observes and reports.
  - Anything read from tool_input, the transcript, or the provider session.
  - Falling back to process inspection when the environment says nothing.

# Acceptance criteria
- AC1: The hook derives a terminal program and a session identifier from its inherited environment, with an absent variable yielding no field rather than a guess.
- AC2: The values pass the existing sanitisation and length limits before entering the alert.
- AC3: structured_details documents the added fields and why they are metadata rather than content, in the same terms as what it already refuses.
- AC4: The alert carries the fields to the spool and a companion that predates them is unaffected.
- AC5: Notification tests cover a session with an identity, one without, and one whose variables hold unusable values.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: The hook derives a terminal program and a session identifier from its inherited environment, with an absent variable yielding no field rather than a guess.
- request-AC6 -> This backlog slice. Proof: AC2: The values pass the existing sanitisation and length limits before entering the alert.
- request-AC7 -> This backlog slice. Proof: AC3: structured_details documents the added fields and why they are metadata rather than content, in the same terms as what it already refuses.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_040_alerts_that_lead_back_to_their_terminal`
- Architecture decision(s): (none yet)
- Request: `req_053_bring_back_the_terminal_an_alert_came_from`
- Primary task(s): `task_064_deliver_alerts_that_lead_back_to_their_terminal`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
