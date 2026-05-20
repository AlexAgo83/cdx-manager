# Changelog (`0.4.4 -> 0.5.0`)

Release date: 2026-05-20

## Major Highlights

- Added session disable/enable controls so an assistant can be kept in the registry while temporarily removed from launch rotation.
- Added shared workspace context commands to make provider/account handoff explicit when moving between Codex and Claude sessions.
- Prepared the package metadata for the 0.5.0 release across npm, PyPI, CLI version output, and README install examples.

## Session Disable Toggle

- Added `cdx disable <name> [--json]` and `cdx enable <name> [--json]`.
- Disabled sessions remain visible in the main list and status views with a `disabled` status.
- Disabled sessions sort after enabled sessions and are excluded from status priority recommendations.
- Launching a disabled session now fails with a clear `Session is disabled: <name>` error.
- Claude live status refresh skips disabled sessions.

## Shared Context Handoff

- Added per-workspace shared context storage at `~/.cdx/contexts/<workspace-hash>/context.md`.
- Added `cdx context show`, `path`, `init`, `edit`, `clear`, and `set`.
- Added `cdx handoff <name>` to install the current workspace context into the target session as `shared-context.md` before launching it.
- Added `cdx handoff <name> --json` for non-interactive integrations that only need to install the context and inspect the resulting paths.
- Reserved `context` and `handoff` as session names to avoid command collisions.

## Packaging

- Bumped `package.json`, `package-lock.json`, `pyproject.toml`, and `src/cli.py` to `0.5.0`.
- Updated the README version badge, pinned installer example, command table, JSON command list, and data layout notes.
- Removed the accidental npm self-dependency from `package.json` and regenerated the lockfile.

## Validation and Regression Coverage

- Added CLI coverage for context storage, workspace isolation, and handoff installation.
- Added session-service coverage for disabled-session ordering, launch blocking, and new reserved command names.
- Kept the full Python test suite green.

## Validation and Regression Evidence

- `python -m pytest`
- `npm run lint`
- `npm test`
- `node bin/cdx.js --version`
- `npm pack --dry-run`
