# CDX Manager 0.20.13

## Launches no longer open with a message you never typed

- RTK and Logics guidance used to be passed as the provider's positional prompt,
  which Claude Code and Codex submit as a user turn: a bare `cdx <session>`
  opened with that guidance shown as your message plus a model reply to it, and
  every resume sent it again as a new message.
- Claude now receives the guidance through `--append-system-prompt`, and Codex
  through `-c developer_instructions=...`. Launch, resume, and headless runs are
  all covered, and no turn is ever submitted on your behalf.
- Codex guidance is appended after any `developer_instructions` already set in
  the profile's `config.toml` rather than replacing it. When that value cannot be
  read (Python older than 3.11 without `tomli`), cdx leaves it untouched and adds
  no guidance.
- Antigravity has no instruction channel and, like Ollama, no longer receives
  the guidance.
- `cdx doctor --check-provider-flags` now verifies the options used to pass it.

## Logics update hint

- The update notice now suggests `logics-manager update` instead of the legacy
  `logics-manager self-update` alias.

## Validation

- 1055 Python tests and project lint pass.
- Verified against real CLIs on macOS, Linux (WSL), and Windows: Claude Code
  (2.1.177, 2.1.283) and Codex CLI (0.156.1, 0.157.1) receive the guidance, and
  interactive launches and resumes no longer add a user turn to the provider
  transcript, where 0.20.12 added one. Codex guidance also survives a resumed
  thread and merges with a profile's own `developer_instructions`.
