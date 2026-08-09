## task_041_orchestrate_agent_completion_notifications - Orchestrate agent completion notifications
> From version: 0.15.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-09 18:50:13
> Owner: Claude (Opus 5)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Confirm what each provider actually reports and how it hands the payload over: Claude Code's `Stop` and `Notification` hooks write JSON to standard input, Codex's `notify` passes it as a command-line argument. Supporting one shape looks like working code while covering half the providers.
- [x] 2. Confirm the two paths before writing to them: Codex's config is `<authHome>/config.toml` because `CODEX_HOME` is `authHome` itself, and the hook command must be a resolved cdx path rather than the bare name, since Codex spawns it without a shell and a Windows npm install ships a `.cmd` shim.
- [x] 3. Verify that Claude Code honours hooks found in a `settings.json` written by something other than itself, rather than holding them pending an approval the user never sees. If an approval is involved, provisioning is not done until that is handled.
- [x] 4. Retire the `--at-reset`/`--next-ready` parsing and README rows, checking that `cdx ready` and its scheduling path are untouched, so the name is free before anything is built on it.
- [x] 5. Write the PowerShell toast snippet and confirm it surfaces in the notification centre, since a toast without a valid `AppUserModelID` is dropped silently and would otherwise look like working code. Reach it from both native Windows and WSL as one snippet with two entry points rather than writing the platform logic twice.
- [x] 6. Leave the Linux path alone beyond attributing notifications to cdx; `notify-send` is already correct and already bounded at five seconds.
- [x] 7. Build `cdx notify` as the hook target over the existing `send_desktop_notification`, reading the session name from the launch environment and swallowing every failure.
- [x] 8. Suppress notifications on the headless run path through the same environment variable that carries the session name, and confirm a scripted sequence of runs stays silent while an interactive launch still notifies.
- [x] 9. Add the idempotent provisioning and revocation into the launch path, marking cdx's own entries so they can be recognized and removed without touching user-authored ones.
- [x] 10. Add the `--notify on|off` launch setting alongside the existing on/off settings, defaulting to on.
- [x] 11. Verify the end-to-end case the request exists for: two sessions launched in two different repositories, each producing a notification that names itself.
- [x] 12. Check the failure paths deliberately — no notifier binary, unreadable or unwritable configuration, malformed payload in either shape, a WSL distribution with interop disabled, an undismissed Windows notification — confirming none reaches the user as a launch or turn error, and none holds a turn open.
- [x] 13. Verify each delivery path on the host that can exercise it: macOS locally; native Windows and WSL on the tower, one machine reachable as `aagos@kdesktop` for the Windows side and `ssh aagos@kdesktop "wsl.exe -d Ubuntu -u aagos -- ..."` for the WSL side. Split each remote check into the part assertable over SSH — exits, exits promptly, reports no error — and the one part that is not: whether the notification appeared. That single line is the gate for the Windows and WSL acceptance criteria, since a clean exit code is exactly what a silent AUMID rejection also looks like.
- [x] 14. Add a changelog entry for the breaking retirement of the previous `cdx notify` surface, without touching the version declarations: releases are their own commit here.
- [x] 15. Update the README's notification and command-reference sections, and reconcile the `cdx ready` description that currently refers to `cdx notify`.
- [x] 16. Run the notify and CLI test files, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_073_reassign_cdx_notify_to_the_agent_event_hook_target`
- `item_074_provision_and_revoke_provider_hooks_in_each_session_s_home_at_launch`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: Real turns on both providers sent `hook_event_name`/`cwd` on stdin; each raised a notification naming the session. Validated with `python3 -m pytest test/` (663 passed) and `ruff check src/ test/`. Source: `5a7d3d5`
- request-AC6 -> This task. Proof: Different sessions and repositories produced different titles and bodies; covered by test_parallel_sessions_are_distinguishable. Validated with `python3 -m pytest test/` (663 passed) and `ruff check src/ test/`. Source: `5a7d3d5`
- request-AC7 -> This task. Proof: `cdx notify --at-reset` no longer reaches the quota flow, `cdx ready --json` is unchanged, and the retired flags are gone from help, usage and README. Validated with `python3 -m pytest test/` (663 passed) and `ruff check src/ test/`. Source: `5a7d3d5`
- request-AC8 -> This task. Proof: Malformed payloads, a raising notifier and the tower's Windows-only Codex all returned cleanly without failing a launch. Validated with `python3 -m pytest test/` (663 passed) and `ruff check src/ test/`. Source: `5a7d3d5`
- request-AC2 -> This task. Proof: Launches provisioned `rose` (Claude, settings.json) and `work1`/`main` (Codex, generated plugin outside CODEX_HOME); the Codex hook fired only with the plugin outside the home. Validated with `python3 -m pytest test/` (663 passed) and `ruff check src/ test/`. Source: `5a7d3d5`
- request-AC3 -> This task. Proof: Re-provisioning returned False with files unchanged; `rose`, `work1` and `main` were pre-existing sessions provisioned with no migration step. Validated with `python3 -m pytest test/` (663 passed) and `ruff check src/ test/`. Source: `5a7d3d5`
- request-AC4 -> This task. Proof: `rose`'s settings.json kept its rtk PreToolUse hook and four unrelated settings through install and removal. Validated with `python3 -m pytest test/` (663 passed) and `ruff check src/ test/`. Source: `5a7d3d5`
- request-AC5 -> This task. Proof: `cdx set claudetest --notify off` stored `notify: false` and showed `Notify off`; `cdx unset --notify` restored it. Validated with `python3 -m pytest test/` (663 passed) and `ruff check src/ test/`. Source: `5a7d3d5`
- request-AC9 -> This task. Proof: The Windows toast was raised on the tower and seen on screen; the blocking MessageBox is deleted. Validated with `python3 -m pytest test/` (663 passed) and `ruff check src/ test/`. Source: `5a7d3d5`
- request-AC10 -> This task. Proof: Implemented across f5361a5, 6da3f15 and bc29f63; validated with python3 -m pytest test/ (661 passed) and ruff check src/ test/. Delivery verified live on all three platforms: macOS confirmed on screen, native Windows and WSL-over-interop toasts both confirmed on the tower. Source: `bc29f63`
- request-AC11 -> This task. Proof: Implemented across f5361a5, 6da3f15 and bc29f63; validated with python3 -m pytest test/ (661 passed) and ruff check src/ test/. Delivery verified live on all three platforms: macOS confirmed on screen, native Windows and WSL-over-interop toasts both confirmed on the tower. Source: `bc29f63`
- request-AC12 -> This task. Proof: Implemented across f5361a5, 6da3f15 and bc29f63; validated with python3 -m pytest test/ (661 passed) and ruff check src/ test/. Delivery verified live on all three platforms: macOS confirmed on screen, native Windows and WSL-over-interop toasts both confirmed on the tower. Source: `bc29f63`
- request-AC13 -> This task. Proof: Implemented across f5361a5, 6da3f15 and bc29f63; validated with python3 -m pytest test/ (661 passed) and ruff check src/ test/. Delivery verified live on all three platforms: macOS confirmed on screen, native Windows and WSL-over-interop toasts both confirmed on the tower. Source: `bc29f63`
- request-AC14 -> This task. Proof: Implemented across f5361a5, 6da3f15 and bc29f63; validated with python3 -m pytest test/ (661 passed) and ruff check src/ test/. Delivery verified live on all three platforms: macOS confirmed on screen, native Windows and WSL-over-interop toasts both confirmed on the tower. Source: `bc29f63`
- request-AC15 -> This task. Proof: Implemented across f5361a5, 6da3f15 and bc29f63; validated with python3 -m pytest test/ (661 passed) and ruff check src/ test/. Delivery verified live on all three platforms: macOS confirmed on screen, native Windows and WSL-over-interop toasts both confirmed on the tower. Source: `bc29f63`
- request-AC16 -> This task. Proof: Implemented across f5361a5, 6da3f15 and bc29f63; validated with python3 -m pytest test/ (661 passed) and ruff check src/ test/. Delivery verified live on all three platforms: macOS confirmed on screen, native Windows and WSL-over-interop toasts both confirmed on the tower. Source: `bc29f63`
- request-AC17 -> This task. Proof: Implemented across f5361a5, 6da3f15 and bc29f63; validated with python3 -m pytest test/ (661 passed) and ruff check src/ test/. Delivery verified live on all three platforms: macOS confirmed on screen, native Windows and WSL-over-interop toasts both confirmed on the tower. Source: `bc29f63`
- request-AC18 -> This task. Proof: Implemented across f5361a5..5a7d3d5 and verified on real turns of both providers: Claude Code on session rose (macOS), Codex on work1 (macOS) and main (tower WSL), with delivery confirmed on screen for macOS, native Windows and WSL-over-interop. Validated with python3 -m pytest test/ (663 passed) and ruff check src/ test/. Source: `5a7d3d5`

# Validation
- (no validation recorded yet)
- command: `python3 -m pytest test/ && python3 -m ruff check src/ test/` | result: passed | date: 2026-08-09
- Finish workflow executed on 2026-08-09.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-09.
- Linked backlog item(s): `item_073_reassign_cdx_notify_to_the_agent_event_hook_target`, `item_074_provision_and_revoke_provider_hooks_in_each_session_s_home_at_launch`
- Related request(s): `req_030_tell_the_user_which_parallel_cdx_session_finished_or_is_waiting_without_watching_terminals`

# AI Context
- Summary: Orchestrate agent completion notifications
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_030_tell_the_user_which_parallel_cdx_session_finished_or_is_waiting_without_watching_terminals`
- Product brief(s): `prod_020_know_which_parallel_session_needs_you`
- Architecture decision(s): (none yet)
