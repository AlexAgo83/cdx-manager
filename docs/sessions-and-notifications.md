# Sessions and notifications

## Agent notifications

When a session's agent finishes a turn, or stops to wait for you, cdx raises a
desktop notification naming the session and the repository:

```text
✓ work1     logics-manager · needs your attention
✓ codex-a   cdx-manager · turn complete
```

CDX asks once at the first eligible interactive launch before writing a provider hook. Consent is installation-wide, but each profile receives its hook only when it is next launched. Alert delivery then starts muted; use `cdx tray alerts on` when you want banners. The older per-session commands remain compatible:

```bash
cdx set work1 --notify on      # turn it on for one session
cdx set --all --notify on      # turn it on everywhere
cdx set work1 --notify off     # and back off; cdx removes what it installed
cdx set work1 --notify-preview on  # include a short final-response preview
```

Turning it on records the setting. The wiring happens at that session's **next
launch**: cdx writes the hook into the session's own home and says so once.
Claude Code honours it straight away. Codex only runs hooks that come from an
installed plugin, so cdx generates one per session and installs it — and Codex
asks you to approve it once, which cdx leaves to you rather than writing that
trust on your behalf.

It is off by default because turning it on writes into the provider's own
configuration and, on Codex, puts an approval prompt in front of you. That is
not something to do to sessions you already own without being asked.

New sessions inherit response previews when agent alerts were accepted during
tray installation. A completion notification includes at most 180 characters
of the agent's final response, and a permission request may quote the
provider's own one-line description of what it wants to do. That text can be
visible on a lock screen; disable it per session with
`cdx set <name> --notify-preview off`. Previews never read transcripts, and the
command a permission request is about is never included.

Both providers are subscribed to the same two alerting hooks: `Stop` when a turn
ends and `PermissionRequest` when one blocks on your approval, plus
`UserPromptSubmit`, which raises no alert and only feeds the agent state below. Claude Code is also
subscribed to `Notification`, for the "still waiting for you" states that no
other hook reports; the permission notifications it also sends are dropped,
because `PermissionRequest` already reported the same call immediately and by
name.

Claude Code additionally reports a turn that ended on a provider error rather
than on an answer — a rate limit, an overload, an authentication or billing
problem. Those alerts are marked apart from completions, name the error class,
and say whether the failure is one that usually clears on its own or one that
needs you. Codex documents no equivalent hook, so a Codex turn killed by its
provider stays silent; that is a gap in what the provider publishes, not a
setting.

A running tray companion receives each alert as fields rather than as a
sentence, so its menu can name the session, the project and the tool, and
clicking a recent alert opens the session it came from. The tool's arguments,
the transcript path and the provider's own session identifiers are never part of
that — only what cdx already knew and what the providers document as safe
metadata.

`cdx notify` is the internal hook target, called by the provider; it is not the
setup command. `cdx ready` is separate: it notifies you when the next cooling-
down session becomes usable.

Per platform: macOS uses `osascript`, Linux `notify-send`, Windows a toast, and
WSL reaches the Windows notification centre through interop. On a host with no
way to deliver one — a headless or SSH Linux session, or WSL with interop
disabled — cdx installs no hooks at all rather than asking you to approve
something that could show you nothing. Headless `cdx run` never notifies: its
caller already learns of completion from the return value.

## Agent state

Every hook event `cdx notify` receives also rewrites one small record for that
session under `$CDX_HOME/state/agents/<session>.json`, whether alerts are on,
muted or off. `cdx agents` lists them, so a dashboard, a chat agent or a
terminal board can ask which sessions are working, waiting for you, done,
failed or stopped by a usage limit without reading transcripts or terminals:

```bash
cdx set work1 --agent-state on   # hooks for state only, no desktop alerts
cdx agents                       # table, waiting sessions first
cdx agents --json                # the same for scripts
cdx agents --max-age-hours 4     # drop records older than 4 hours (default 24)
```

Sessions with `--notify on` keep state already; `--agent-state on` is for
sessions that want state without banners. It installs the same hooks, and it
installs them even where no notification could be shown (an SSH login, a
headless WSL), since a remote dashboard is exactly what watches those.

| State | Set by |
| --- | --- |
| `working` | a prompt was submitted (`UserPromptSubmit`) |
| `waiting` | a permission request, or Claude's idle or needs-input notification |
| `done` | the turn ended (`Stop`) |
| `failed` | the turn ended on a provider error (Claude's `StopFailure`); `reason` is the error class |
| `limit` | that error says the account ran out and the account's own refreshed status agrees, the same two-signal rule as `cdx run --failover`; `reset_at` is the account's reset time when known |
| `ended` | computed by `cdx agents`: the cdx process that launched the session is gone; `last_state` keeps what it was |

`cdx agents --json` returns `{"ok": true, "action": "agents", "max_age_hours": 24,
"agents": [...]}`, each entry carrying `session`, `provider`, `cwd`, `project`,
`state`, `reason`, `prompt`, `reset_at`, `pid` and `updated_at` (ISO 8601, UTC).
`prompt` is the head of the last prompt, at most 120 characters, and only for
sessions with `--notify-preview on`; otherwise it is `null`. Records older than
the maximum age are deleted when listed.

A waiting session stays `waiting` until its next prompt or the end of the turn:
cdx does not subscribe to every tool call to notice that you answered. A Codex
profile whose cdx plugin was installed before this release keeps its old hooks
(no `working` state) until the plugin is reinstalled with `cdx set <name>
--notify off`, a launch, then `--notify on` and another launch.

Use `cdx ready` when every useful assistant is cooling down and you want your terminal back. cdx picks the next known reset, registers a native OS notification, and exits immediately. If no future reset is known, it exits successfully and explains that no notification was scheduled.

```bash
cdx ready
cdx ready --refresh
```

## Persistent Launch Settings

New sessions start with `power=medium` and `fast=off`, so launches are predictable without enabling fast mode. Set or override only the values you want to pin:

```bash
cdx set work --power medium --permission full --fast off
cdx set personal --power low --permission review
cdx set --sessions all --permission auto
cdx set --provider ollama --model llama3.2
cdx set work --priority 80
cdx set work --rtk on
cdx set work --logics off
cdx power all low
cdx perm provider:claude review
cdx model provider:ollama llama3.2
cdx config work
cdx configs
```

Those values are stored on the session and reapplied every time you run `cdx work`. Remove overrides to return to provider-native defaults:

```bash
cdx unset work --power
cdx unset --sessions work,personal --fast
cdx unset --provider claude --permission
cdx unset work --priority
cdx unset work --rtk
cdx unset work --logics
cdx unset work --all
cdx power all default
cdx model provider:ollama default
```

`--model` maps to Codex `--model`, Claude `--model`, and Ollama `ollama run <model>`. `--power` maps to Codex `model_reasoning_effort` and Claude `--effort`; supported values are `minimal`, `low`, `medium`, `high`, and `xhigh`. `--permission` maps to provider-native permission flags. Codex Fast mode is separate from reasoning effort: `--fast on` opts a Codex session into the Codex Fast service tier, while new sessions, `--fast off`, and default launches force the non-Fast `flex` tier. Use `--power low` when you want low reasoning effort without enabling Codex Fast credits. Existing legacy sessions that stored `fast=on` before this split continue to behave as low effort unless the user explicitly sets `--fast on` again. `--priority` is a 0..100 selector preference used as a tie-breaker after readiness and availability. `--policy use|ask-first|never` (default `use`) says whether cdx may pick an account on your behalf: `cdx next`, `cdx select`, `cdx run --provider` and run failover only ever choose `use` accounts; `ask-first` accounts are offered by `cdx rescue` with a confirmation, `never` accounts are not offered at all. Naming an account explicitly (`cdx <name>`, `cdx run <name>`) is always allowed. `--rtk on` adds standing guidance that encourages assistants to use RTK (`rtk <command>`) for noisy terminal commands when RTK is available, while keeping raw commands for exact output. Logics guidance is auto-enabled when `logics-manager` is available; use `--logics off` to disable that guidance for a session, or `--logics on` to pin it explicitly. This guidance is passed as instructions, never as a first message: Claude receives it through `--append-system-prompt` and Codex through `-c developer_instructions=...`, appended after any `developer_instructions` already set in the profile's `config.toml` (on Python older than 3.11 without `tomli`, a profile that sets its own is left untouched and gets no cdx guidance). Launching or resuming a session therefore never submits a turn on your behalf. Antigravity and Ollama have no instruction channel and receive no guidance. Whatever the `--rtk` setting, every launch, resume and `cdx run` sets `RTK_DB_PATH` to the rtk history of your real home (`~/Library/Application Support/rtk/history.db` on macOS, `~/.local/share/rtk/history.db` on Linux, `%LOCALAPPDATA%\rtk\history.db` on Windows), so `rtk gain` in your own shell counts what every account saved instead of each profile keeping its own; an `RTK_DB_PATH` you set yourself is kept. If you also pass `--append-system-prompt` through `--extra-args`, Claude receives the option twice; prefer putting your own text in the profile's `CLAUDE.md`.

## Terminal Titles

Interactive launches and resumes set the terminal window title to `session — folder`, where `folder` is the basename of the launch directory - for example `work — cdx-manager`. The convention is identical for Claude, Codex, and Antigravity: it comes from the shared launch runtime, not from provider flags, and cdx keeps re-asserting it so a provider TUI cannot take the title back mid-session.

The title is only written when stdout is a terminal. Nothing is emitted for `--json` launches, redirected or piped output, `cdx run` and other headless runs, login flows, or Ollama sessions. Session names and directories are stripped of escape and control characters before the title is emitted, and cdx does not restore the previous title when the session ends.

Claude Code writes its own animated title while an action runs, and it redraws far more often than cdx re-asserts the shared title. So interactive Claude launches and resumes started by cdx set the Claude-specific `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` in the provider environment, which stops Claude from setting and clearing the title and leaves `session — folder` stable while Claude is busy. Claude's in-TUI activity indicator is unaffected, the value is forced so an ambient setting in your shell cannot hand the title back, and headless `cdx run`, Claude authentication flows, and every non-Claude provider keep their previous environment.

## Launch History

Every interactive `cdx <name>` launch is recorded under `CDX_HOME`, including success/failure, duration, cwd, launch settings, and transcript path.

```bash
cdx history
cdx history work
cdx history work --limit 5
cdx history work --json
cdx history --summary
cdx history --summary --since 7d
cdx history --summary --from 2026-05-01 --to 2026-05-28
```

`cdx history --summary` aggregates total time per assistant. Add `--since`, `--from`, or `--to` to focus on a period.
