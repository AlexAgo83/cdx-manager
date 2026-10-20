# Release 0.21.4 preparation

Prepared locally on 2026-10-20. The checked-in release notes are `changelogs/CHANGELOGS_0_21_4.md`; the GitHub release title is the tag, `v0.21.4`.

## Scope

- `cdx <name> --prompt` / `--prompt-file` (#13), refused for Ollama sessions.
- Claude spawns drop session markers inherited from a parent Claude Code session (#14).
- Initial prompts passed after `--` for Claude, Codex and Ollama (interactive launch, handoff, `cdx run`).
- Version metadata and README badge aligned to 0.21.4.

## Local receipts

- `npm test`: 1086 passed. `npm run lint`: passed. `logics-manager lint`: OK.
- `--` handling checked against the real CLIs on macOS: claude 2.1.304 and codex-cli 0.163.0 print their help for a positional `-h` and take it as the prompt after `--`; ollama takes the argument after `--` as the prompt. Antigravity is unaffected (Go `flag` always takes the next argument as the `--prompt-interactive` value).
