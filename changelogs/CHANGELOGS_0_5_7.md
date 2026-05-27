# Changelog (`0.5.6 -> 0.5.7`)

Release date: 2026-05-27

## Major Highlights

- Added persistent per-session launch settings for Codex and Claude assistants.
- Let users pin power, permission, and fast-mode preferences once and have `cdx` reapply them on every launch.
- Preserved native provider defaults when no launch settings are configured.

## Launch Settings

- Added `cdx set <name>` with `--power`, `--permission`, and `--fast` options.
- Added `cdx config <name>` to inspect the launch settings stored on a session.
- Added `cdx unset <name>` to clear individual launch settings or all overrides with `--all`.
- Stored launch settings directly on each CDX session record.
- Copied launch settings when copying a session.
- Exported and imported launch settings with session bundles.

## Provider Runtime

- Mapped Codex power settings to `model_reasoning_effort`.
- Mapped Claude power settings to `--effort`.
- Mapped Codex permission presets to sandbox and approval flags.
- Mapped Claude permission presets to `--permission-mode`.
- Treated `--fast on` as low effort when no explicit power setting is configured.

## CLI Output and Documentation

- Added launch settings to `cdx --help`.
- Added a compact launch-settings column to `cdx` session listings when any session has overrides.
- Documented the persistent launch-settings workflow in the README.
- Updated package metadata, CLI version output, README badge, and pinned installer example to `v0.5.7`.

## Validation and Regression Coverage

- Added regression coverage for persistent Codex launch settings and `unset --all`.
- Added regression coverage for persistent Claude launch settings and `cdx config`.
- Added runtime coverage for `fast on` resolving to low effort when no power is configured.

## Validation and Regression Evidence

- `python -m py_compile bin/cdx src/*.py test/test_*_py.py`
- `python -m unittest discover -s test -p 'test_*_py.py'`
- `npm pack --dry-run`
