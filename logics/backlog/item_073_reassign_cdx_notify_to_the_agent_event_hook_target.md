## item_073_reassign_cdx_notify_to_the_agent_event_hook_target - Reassign cdx notify to the agent-event hook target
> From version: 0.15.1
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Notifications
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-09 17:16:24

# Problem
- There is no command a provider hook can call to raise a cdx notification. The providers can run an arbitrary command on a turn event, but cdx offers no target for it.
- The name `cdx notify` is held by the quota-reset flow, whose question — when does my quota come back — is already answered by `cdx status`, and whose only form anyone types is `cdx ready`.
- A notification that does not name the session and the repository is useless in the case that motivates the feature, and only cdx knows the session name.

# Scope
- In:
  - Make `cdx notify` read a hook payload from standard input, tolerate an absent, empty, or malformed payload, and raise a notification through the existing `send_desktop_notification`.
  - Compose the message from the cdx session name, the basename of the working directory the agent ran in, and the kind of event, so parallel sessions are distinguishable at a glance.
  - Resolve the session name from the launch environment, since the hook runs as a child of the launched provider and inherits it.
  - Distinguish the two events the providers report — a turn that ended and an agent waiting for input — in the message text.
  - Exit successfully whatever happens, so a hook failure never surfaces to the user as a provider error.
  - Replace the Windows notifier's blocking `MessageBox` with a non-blocking delivery, and bound it in time the way the macOS and Linux paths already are, since as a per-turn hook an undismissed dialog holds the turn open indefinitely.
  - Treat a host with no usable notification channel — a headless or SSH Linux session with no D-Bus, an SSH macOS session — as silence rather than as an error, and state it in the README so it is a known outcome.
  - Retire the `--at-reset` and `--next-ready` argument parsing and its usage string, and remove the corresponding README rows.
  - Keep `cdx ready` and the scheduling internals it depends on working unchanged.
- Out:
  - No deletion of the quota-reset scheduling backends.
  - No change to `cdx ready`'s behavior or output.
  - No delivery channel other than the desktop notifier already present.
  - No message customization.
  - No fallback delivery channel when the desktop channel is unavailable; silence is the accepted outcome.

# Acceptance criteria
- Given a hook payload on standard input naming a working directory, `cdx notify` raises a notification whose text contains the cdx session name and that directory's basename.
- Given two sessions notifying from two different repositories, the two messages differ in both the session name and the directory name.
- Given a turn-ended event and a waiting-for-input event, the two notifications are distinguishable by their text.
- Given empty, truncated, or non-JSON input, `cdx notify` exits successfully without raising an error to the caller.
- Given no notifier binary available on the platform, `cdx notify` exits successfully and raises nothing.
- Given `cdx notify --at-reset` or `cdx notify --next-ready`, the command no longer offers that behavior, and the README no longer documents it.
- Given a notification on Windows that the user never dismisses, the hook process still exits and the agent turn is not held open.
- Given a Linux host with no session bus, `cdx notify` exits successfully, raises nothing, and the agent turn completes normally.
- Given `cdx ready`, the behavior and output are identical to before this change.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Given a hook payload on standard input naming a working directory, `cdx notify` raises a notification whose text contains the cdx session name and that directory's basename.
- request-AC6 -> This backlog slice. Proof: Given two sessions notifying from two different repositories, the two messages differ in both the session name and the directory name.
- request-AC7 -> This backlog slice. Proof: Given a turn-ended event and a waiting-for-input event, the two notifications are distinguishable by their text.
- request-AC8 -> This backlog slice. Proof: Given empty, truncated, or non-JSON input, `cdx notify` exits successfully without raising an error to the caller.
- request-AC9 -> This backlog slice. Proof: Given a notification on Windows that the user never dismisses, the hook process still exits and the agent turn is not held open.
- request-AC11 -> This backlog slice. Proof: Given a Linux host with no session bus, `cdx notify` exits successfully, raises nothing, and the agent turn completes normally.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_020_know_which_parallel_session_needs_you`
- Architecture decision(s): (none yet)
- Request: `req_030_tell_the_user_which_parallel_cdx_session_finished_or_is_waiting_without_watching_terminals`
- Primary task(s): `task_041_orchestrate_agent_completion_notifications`

# AI Context
- Summary: Reassign cdx notify to the agent-event hook target
- Keywords: scaffolded-backlog, reassign cdx notify to the agent-event hook target, implementation-ready
- Use when: Implementing the scaffolded slice for Reassign cdx notify to the agent-event hook target.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
