# CDX Manager 0.25.2

Release date: 2026-10-31

This patch release improves usage attribution and makes unverifiable run budgets fail explicitly.

## Fixes

- Preserve observed Codex model evidence for usage pricing. Keep costs unknown when model evidence is missing or mixed without per-model counters, and fail unverifiable budgets with `budget_unverifiable` and exit code 125. (#76)
- Attribute CDX usage to canonical source repositories so project statistics group runs by their source repository rather than isolated execution directories. (#75)

## Maintenance

- Record tray companion checksums for v0.25.1. (`e3530977b2b95cd3ec39bbe962725f275fef4370`)
- Record release archive checksums for v0.25.1. (`59b5d276abc5877554d9ffc44b468b53b12dd1d4`)
