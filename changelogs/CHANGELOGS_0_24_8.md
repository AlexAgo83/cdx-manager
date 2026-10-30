# CDX Manager 0.24.8

Release date: 2026-10-30

This patch improves recovery from Codex model capacity failures. (#67)

## Codex capacity recovery

- Retry headless Codex capacity failures after 1 and 2 seconds before trying configured fallback models, then ready Codex profiles in priority-aware order. Recovery also applies to detached runs and does not require `--failover`. (#67)
- Exclude disabled, logged-out, `never`, and `ask-first` profiles from automatic fallback. Limit recovery to three attempts per model and four profile switches, reporting `capacity_recovery_exhausted` when no eligible alternative remains or the budget is exhausted. (#67)
- Log recovery actions to stderr and structured run data, preserve failed attempt output, and report the effective model without changing profile settings. (#67)

## Maintenance

- Record tray companion checksums for v0.24.7. (`16938c0d22de4589f5b4757fd7ff55e848127e7d`)
- Record release archive checksums for v0.24.7. (`a169c3eee41fcbc97477ca4d74bfc8f77c1330d5`)
