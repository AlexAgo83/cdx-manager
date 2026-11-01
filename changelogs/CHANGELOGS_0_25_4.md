# CDX Manager 0.25.4

Release date: 2026-11-01

This patch release measures remote Codex run costs from observed model evidence and applies budgets to those estimates.

## Fixes

- Attribute remote run costs to the model observed in Codex usage evidence rather than the requested model. Preserve that evidence in run tracking, stop runs when measured usage exceeds the budget, and report unverifiable budgets explicitly when reliable model evidence or pricing is unavailable. (#83)

## Maintenance

- Record tray companion checksums for v0.25.3. (`222d5127314bab4200bb13b1b364b3ab5253fb1b`)
- Record release archive checksums for v0.25.3. (`9bac8bf616345e4348507038dc392a51eb0a360f`)
