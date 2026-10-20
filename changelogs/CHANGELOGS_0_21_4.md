# CDX Manager 0.21.4

## Start a session on a first message

- `cdx <name> --prompt TEXT` and `cdx <name> --prompt-file PATH` launch an interactive session that starts on that message, for launcher scripts that open a session already pointed at a task. Both spellings `--flag value` and `--flag=value` work. They are refused before the provider starts when combined with each other, with `--resume` or `cdx resume`, with `--prompt-file -` (the session needs standard input), and for Ollama sessions (`ollama run` answers once and exits). A relative `--prompt-file` path is read from the current directory, not `--dir`. Contributed by Nicolas Rigaudy (#13).

## Fixes

- Claude sessions started from inside a running Claude Code session (a hook, or a terminal or script it spawned) saved no transcript: they inherited the parent's session markers (`CLAUDECODE`, `CLAUDE_CODE_CHILD_SESSION`, ...) and ran as a child session, which broke resume and interactive usage backfill. CDX now drops those markers for every Claude spawn; user settings such as `CLAUDE_CODE_DISABLE_*` still pass through. Contributed by Nicolas Rigaudy (#14).
- A prompt starting with `-` (from `--prompt`, `cdx handoff` or `cdx run`) is now passed after `--`, so Claude, Codex and Ollama no longer read it as an option (for example `-h` printed the provider's help instead of starting).
