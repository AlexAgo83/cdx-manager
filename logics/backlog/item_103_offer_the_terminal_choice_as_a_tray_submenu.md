## item_103_offer_the_terminal_choice_as_a_tray_submenu - Offer the terminal choice as a tray submenu
> From version: 0.18.6
> Schema version: 1.0
> Status: In progress
> Understanding: 95%
> Confidence: 90%
> Progress: 10%
> Complexity: Medium
> Theme: tray-companion
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Expose supported terminal candidates as an immediate, checked native tray submenu.
- Keywords: offer, terminal, choice, tray, submenu
- Use when: Changing native tray menu construction for terminal choice.
- Skip when: Changing candidate discovery or platform launch execution.

# Problem
- The preference is invisible from the tray, which is where the operator is when the wrong terminal opens.
- There is no menu vocabulary yet for a choice among several values; the existing Check is used only for a two-state switch.

# Scope
- In:
  - Build a terminal submenu from the snapshot's candidates, using the existing Entry::Submenu and Entry::Check, with the current choice ticked and an explicit system-default entry.
  - Add a menu action carrying the chosen name, handed back to CDX exactly as the alert mute already does, followed by a repoll so the tick shows what was stored.
  - Wire the action on all three platform backends.
  - Render no submenu at all when the snapshot carries no candidates, rather than an empty heading.
- Out:
  - Composing any launch command inside the companion.
  - Offering a name absent from the snapshot's candidates.
  - Restarting or reopening terminals already open when the choice changes.

# Acceptance criteria
- AC1: The menu shows a terminal submenu whose entries are the snapshot's candidates plus a system-default entry, with exactly one ticked.
- AC2: Clicking an entry writes the preference through CDX and the following poll drives the tick, so a rejected value never appears as selected.
- AC3: The macOS, Linux and Windows backends all dispatch the action.
- AC4: A snapshot with no candidates renders no submenu and no empty heading.
- AC5: The chosen terminal takes effect on the next session row opened, with no companion restart.
- AC6: Menu tests cover the tick, the default entry, the empty case and the fact that a click is not drawn as selected until it is stored.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: The menu shows a terminal submenu whose entries are the snapshot's candidates plus a system-default entry, with exactly one ticked.
- request-AC2 -> This backlog slice. Proof: AC2: Clicking an entry writes the preference through CDX and the following poll drives the tick, so a rejected value never appears as selected.
- request-AC4 -> This backlog slice. Proof: AC3: The macOS, Linux and Windows backends all dispatch the action.
- request-AC8 -> This backlog slice. Proof: AC4: A snapshot with no candidates renders no submenu and no empty heading.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_039_a_tray_whose_terminal_preference_is_discoverable_and_honest`
- Architecture decision(s): (none yet)
- Request: `req_052_let_the_operator_choose_the_tray_s_target_terminal_on_every_platform`
- Primary task(s): `task_063_deliver_a_discoverable_and_honest_tray_terminal_choice`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
