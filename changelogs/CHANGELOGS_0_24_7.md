# CDX Manager 0.24.7

Release date: 2026-10-29

This patch fixes command execution in isolated Codex workspace runs. (#65)

## Workspace runs

- Drop Codex's nested sandbox when `--isolate-workspace` is enabled, avoiding the user namespace mapping failure that prevented commands from running. The outer workspace sandbox remains the isolation boundary. (#65)
- Remove Codex's sandbox mode and network overrides inside the isolated workspace and pass `--dangerously-bypass-approvals-and-sandbox`; the outer sandbox controls network access and keeps review runs read-only through its workspace mount. (#65)

## Codex capacity recovery

- Retry headless Codex model capacity failures after 1 and 2 seconds before trying configured fallback models, then ready Codex profiles in the existing priority-aware order. This also applies to detached runs and does not require `--failover`.
- Exclude disabled, logged-out, `never`, and `ask-first` profiles from automatic fallback. Bound recovery to three attempts per model and four profile switches, with a distinct `capacity_recovery_exhausted` outcome.
- Log each recovery action to stderr and structured run data, preserve failed attempt output, and report the effective model without changing profile settings.
- Cover capacity detection, retry and profile budgets, fallback order, selection policies, and backoff cancellation with tests.

## Maintenance

- Record tray companion checksums for v0.24.6. (`87aba5d2cffdfb1a96e386abcdabe54df9ee4808`)
- Record release archive checksums for v0.24.6. (`6b92094143ea28bf0cc096aef88d1015565aba18`)
