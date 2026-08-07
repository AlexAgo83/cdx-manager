"""Per-domain command modules.

Each module owns one group of `handle_*` entry points plus the helpers used
only by that group. `cli_commands` re-exports them so existing imports of
`src.cli_commands` keep resolving; see `src/cli.py` for the same convention.
"""
