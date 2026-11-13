# CDX Manager 0.27.2

Release date: 2026-11-13

## Improvements

- Agents launched through cdx no longer stop on trust prompts. Before every
  interactive launch, resume, handoff and run that uses the profile's home,
  cdx records trust in the provider's own configuration (#143):
  - `cdx set <name> --auto-trust-folder on|off` (default on) trusts the launch
    folder: Claude Code's project trust, Codex's `trust_level = "trusted"`
    and Antigravity's trusted workspaces.
  - `cdx set <name> --auto-trust-hooks on|off` (default on) approves Codex
    hooks with the hashes Codex itself computes, so the "Hooks need review"
    screen no longer appears.
  - Writes merge into the existing files, are atomic and idempotent, touch
    only the launched profile, and leave an unreadable file unchanged with a
    warning.
- `cdx set <name> --codex-update-prompt on|off` (default off) keeps Codex
  from stopping on its "Update available" screen at startup; cdx already
  updates Codex itself (#143).
