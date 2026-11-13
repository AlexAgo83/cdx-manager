## item_171_prove_the_remote_messaging_loop_on_linux_macos_and_windows - Prove the remote messaging loop on Linux, macOS and Windows
> From version: 0.26.14
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: remote-session-control
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: prove, remote, messaging, loop, linux, macos, windows
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- Process control, sockets and terminals differ per platform; a Linux-only proof would not hold.

# Scope
- In:
  - Fake-provider tests for the switch loop, queue, interrupt, endpoint access and event mapping, run in CI on the three platforms.
  - A documented live check script against the real Claude and Codex CLIs, run once per platform before release.
- Out:
  - Live provider calls in CI.

# Acceptance criteria
- AC6: Existing suites stay green with the feature disabled.
- AC7: The new tests pass on the three platforms and the live check is recorded for each.

# AC Traceability
- request-AC6 -> This backlog slice. Proof: AC6: Existing suites stay green with the feature disabled.
- request-AC7 -> This backlog slice. Proof: AC7: The new tests pass on the three platforms and the live check is recorded for each.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_058_remote_control_of_interactive_sessions_through_provider_protocols`
- Architecture decision(s): (none yet)
- Request: `req_083_protocol_based_remote_messaging_for_interactive_sessions`
- Primary task(s): `task_088_implement_protocol_based_remote_messaging_for_interactive_sessions`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |

