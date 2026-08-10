# CDX Manager 0.17.1

## Fixes

### Agent-alert setup now reports provider support accurately

`cdx set <name> --notify on` now distinguishes sessions where cdx can install
provider hooks (Claude and Codex) from providers that do not expose that
integration yet. A mixed bulk selection reports both outcomes instead of
promising a future hook installation that cannot happen.

The setting remains storable for unsupported providers, so bulk configuration
remains predictable and a future provider integration can honour the existing
opt-in.

### Permission-request notifications constrain tool names

Tool names supplied by provider hook payloads now use the same printable,
single-line normalization as response previews and are capped at 80 characters.
This keeps permission notifications readable and prevents malformed payloads
from expanding or controlling desktop notification text.

## Validation

- `npm run lint`
- `npm test`
- `npm run release:validate`
- `logics-manager lint --require-status`
- `logics-manager audit --legacy-cutoff-version 1.1.0 --group-by-doc`
