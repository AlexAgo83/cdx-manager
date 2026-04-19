# Changelog (`0.4.3 -> 0.4.4`)

Release date: 2026-04-20

## Major Highlights

- Generated from the release work on `cdx update`, the first built-in self-update path for `cdx-manager`.
- Added a version-aware update command that can check for a newer release, confirm interactively, and delegate to the right installer for the current installation type.
- Kept the existing update warning behavior intact so the CLI still surfaces newer releases on startup.
- Reserved `update` as a session name to avoid collisions with the new command.

## `cdx update`

- Added `cdx update --check` for a quick release check without applying changes.
- Added `cdx update --yes` for non-interactive environments.
- Added `cdx update --version TAG` so maintainers can target a specific release.
- Routed standalone installs through `install.sh` / `install.ps1`.
- Routed npm installs through `npm install -g cdx-manager@...`.
- Routed Python environment installs through `python -m pip install --upgrade ...`.
- Routed source checkouts through `git pull --ff-only` or an explicit tag checkout when a version is requested.
- Refused source updates when the checkout contains uncommitted changes.

## Validation and Regression Coverage

- Added CLI coverage for update checks, update execution, and version-aware help text.
- Added session-service coverage for the new reserved command name.
- Added unit coverage for installation detection and source-checkout safety in the update planner.
- Kept the existing CLI and session-service test suites green.

## Validation and Regression Evidence

- `python3 -m unittest test.test_cli_py test.test_session_service_py test.test_update_manager_py`
- `npm run lint`
