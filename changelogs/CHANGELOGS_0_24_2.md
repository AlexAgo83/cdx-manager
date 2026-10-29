# CDX Manager 0.24.2

Release date: 2026-10-29

This patch makes busy-session handling explicit and surfaces headless permission denials without marking successful runs as failures.

## Sessions

- Add `--on-busy fail|ask` to session launches and resumes. Use `fail` to refuse a profile with a live session immediately with a non-zero exit and `session_busy` error. The default `ask` keeps interactive confirmation; without a terminal or with `--json`, it refuses the duplicate launch. The policy also works with task, directory, and prompt options. (#55)

## Runs

- Report nonempty Claude `permission_denials` result records as structured run warnings, including the provider and denied tools. A provider exit code of 0 still reports success (`ok: true`), since another tool may have completed the work. Empty or absent denials produce no warning. (#54)
- Clarify that Claude's `--scrub-env on` forces its default permission mode: unattended runs must explicitly allow tools that need approval, using `--allowedTools` through `--extra-args`. (#54)
