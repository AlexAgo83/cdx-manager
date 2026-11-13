# Command reference

## All Commands

| Command | Description |
|---|---|
| `cdx` | List all sessions with last-updated timestamps |
| `cdx --json` | List all sessions as a machine-readable JSON payload |
| `cdx <name>` | Launch a session (checks auth first) |
| `cdx <name> [--on-busy fail\|ask] [--json]` | Launch a session; `--json` returns a structured success payload after the interactive run ends |
| `cdx <name> --on-busy fail` | Refuse a profile with a live session immediately, even with a terminal: non-zero exit and `session_busy` (`error.code` with `--json`). Works with `--task`, `--dir`, prompts and resume; `--on-busy=fail` is also accepted. The default `ask` keeps the confirmation prompt for terminal users; without a terminal or with `--json`, it fails instead of launching a duplicate. Handoff launches and `cdx last` use `ask` too. |
| `cdx <name> --prompt TEXT` / `cdx <name> --prompt-file PATH` | Launch a session that starts on this first message (not with `--resume` or Ollama sessions; `--prompt-file -` is refused because the session needs standard input; a relative `--prompt-file` path is read from the current directory, not `--dir`) |
| `cdx <name> --dir PATH --task TEXT [--end-state TEXT]` | Start a session on a task. `--end-state` names what your go-ahead covers ("CI green on a PR, merged"): the session takes every step it needs, commits, pushes and PRs included, and stops only for a decision outside it. Without `--end-state` it stops and shows the result before any commit, push or PR. Replaces `--prompt`; the first message also tells it to read the repository's instructions and use its skills. |
| `cdx <name> -r` / `cdx <name> --resume` | Resume the provider-native conversation for a session when supported |
| `cdx add [provider] <name> [--model MODEL] [--json]` | Register a new session (`provider`: `codex`, `claude`, `antigravity`, or `ollama`; Ollama requires `--model`). New session names (also for `cp`, `rename` and `import`) must match `[A-Za-z0-9][A-Za-z0-9._-]*`; existing sessions keep their names |
| `cdx cp <source> <dest> [--json]` | Copy a session into another session name, overwriting the destination if it exists |
| `cdx ren <source> <dest> [--json]` | Rename a session and move its auth data |
| `cdx label <name> <label> [--json]` | Attach one short label to a session; tables show `LABEL` only when at least one label exists |
| `cdx label <name> --clear [--json]` | Clear a session label |
| `cdx login <name> [--json]` | Re-authenticate a session (logout + login) |
| `cdx logout <name> [--json]` | Log out of a session |
| `cdx auth claude-token <profile> [--json]` | Store a dedicated remote Claude setup token from stdin in a private controller profile file |
| `cdx auth refresh <name\|all> [--json]` | Make a locked, non-generation Codex auth probe; reports `login_required` when interactive login is needed |
| `cdx disable <name> [--json]` | Disable a session without deleting it; disabled sessions stay visible and cannot launch |
| `cdx enable <name> [--json]` | Re-enable a disabled session |
| `cdx config <name> [--json]` | Show persistent launch settings for a session |
| `cdx configs [--json]` | Show persistent launch settings for all sessions in one table |
| `cdx power\|perm\|fast\|model <name\|all\|provider:PROVIDER\|a,b> <value\|default> [--json]` | Shortcut commands for setting or clearing one launch setting |
| `cdx set <name>\|--sessions all\|a,b\|--provider PROVIDER [--power minimal\|low\|medium\|high\|xhigh] [--permission review\|default\|auto\|full] [--fast on\|off] [--rtk on\|off] [--logics on\|off] [--notify on\|off] [--agent-state on\|off] [--notify-preview on\|off] [--scrub-env on\|off] [--shared-memory on\|off] [--retro on\|off] [--policy use\|ask-first\|never] [--model MODEL] [--fallback-model MODEL[,MODEL...]] [--budget USD] [--extra-args 'ARGS'] [--priority 0..100] [--json]` | Persist launch settings for one or more sessions |
| `cdx unset <name>\|--sessions all\|a,b\|--provider PROVIDER (--power\|--reasoning-effort\|--permission\|--fast\|--rtk\|--logics\|--notify\|--agent-state\|--notify-preview\|--scrub-env\|--shared-memory\|--retro\|--policy\|--model\|--fallback-model\|--budget\|--extra-args\|--priority\|--all) [--json]` | Remove persisted launch settings and fall back to provider defaults |
| `cdx history [name] [--cwd PATH] [--interactive] [--limit N] [--summary] [--since 7d\|today\|DATE] [--from DATE] [--to DATE] [--json]` | Show recent launch history or aggregate total launch time per assistant, optionally filtered by period |
| `cdx history backfill-projects [--mapping FILE] [--dry-run \| --apply] [--json]` | Recover source repository attribution from exact recorded run evidence or an operator mapping; defaults to a read-only preview |
| `cdx history backfill-models [--dry-run \| --apply] [--json]` | Recover missing historical usage models from evidence tied to each run; defaults to a read-only preview |
| `cdx last [--json]` | Launch the most recent existing session from launch history |
| `cdx resume <name> [--conversation <id>] [--json]` | Resume the provider-native conversation for a session using the named command form; `--conversation` reopens that exact conversation and refuses with `conversation_not_found` if the profile has no such transcript |
| `cdx send <name> <text>\|-\|--stdin\|--interrupt\|--status [--json]` | Deliver a message to a live session launched with remote control on; `-` or `--stdin` reads the message from stdin so it never appears in the process list |
| `cdx can-resume <name> [--conversation <id>] [--json]` | Check whether a session supports native resume without launching the provider; `--conversation` checks that exact conversation and reports `resumable: false` with `conversation_not_found` instead of falling back to the most recent one |
| `cdx sessions [--all] --json` | Interactive sessions launched through cdx that are still running (`session`, `provider`, `pid`, `cwd`, `started_at`, `conversation_id`, `profile_dir`, `transcripts_dir`, `processes`); `--all` adds idle enabled accounts so any account's directories can be resolved |
| `cdx context show\|path\|init\|edit\|clear\|set\|append [text...] [--json]` | Manage the shared Markdown context for the current workspace |
| `cdx memory [--global\|--project NAME_OR_PATH] [show\|view\|path\|init\|edit\|clear\|set\|append\|list] [text...] [--json]` | Manage explicit user-controlled memory for the current workspace, global scope, or a named/path project |
| `cdx handoff <name> [--json]` | Reuse the prepared entry for this target/workspace, or use explicitly labelled notes-only recovery if none exists; launch unless `--json` |
| `cdx handoff <source> <target> [--source-conversation ID\|--source-native-transcript PATH\|--source-transcript PATH] [--json]` | Prepare an identity-checked transcript entry and launch the target in the verified workspace unless `--json`; exact native selection resolves duplicate IDs, while explicit terminal selection is degraded recovery |
| `cdx rescue [<session>] [--to <target>] [--yes] [--dry-run] [--json]` | Hand the newest conversation stopped by a usage limit (account at 0%, or a transcript that ends on the provider's usage-limit error; launched in the last 24 h) over to the best ready account of the same provider, in the folder it last ran in. Picks only `--policy use` accounts; falls back to an `ask-first` one with a confirmation; never `never`. Asks before handing off unless `--yes` (which does not cover `ask-first`). `--dry-run` and `--json` show the plan only. A conversation already handed off is not offered again until its session is launched again. |
| `cdx retro [--limit N] [--json]` | Show the latest session retrospectives, newest first (5 by default). Retros run only for sessions with `cdx set <name> --retro on`; see [operations](operations.md#session-retros). |
| `cdx rmv <name> [--force] [--json]` | Remove a session and its auth data (prompts for confirmation unless `--force`) |
| `cdx clean [name] [--yes] [--json]` | Clear launch transcript logs for one session or all sessions after confirmation |
| `cdx clean profiles (--tmp\|--old-logs DAYS) [--yes] [--json]` | Remove explicit profile cleanup candidates after confirmation: temporary marketplace/plugin staging caches or old `.log` files |
| `cdx disk [profiles] [--candidates] [--json]` | Measure `CDX_HOME`; `profiles` includes per-profile breakdown, and `--candidates` reports reclaimable temporary caches and old logs with evidence |
| `cdx reset <name> [--yes] [--json]` | Explicitly consume one available banked Codex rate-limit reset; confirmation is required unless `--yes` is supplied |
| `cdx export <file> [--include-auth] [--sessions a,b] [--passphrase-env VAR\|--passphrase-stdin] [--force] [--json]` | Export sessions to a portable bundle; `--include-auth` encrypts auth data with a passphrase |
| `cdx import <file> [--sessions a,b] [--passphrase-env VAR\|--passphrase-stdin] [--force\|--merge] [--allow-authless-force] [--json]` | Import sessions from a bundle into the current `CDX_HOME` |
| `cdx doctor [--severity OK|WARN|FAIL[,OK|WARN|FAIL...]] [--check-provider-flags] [--json]` | Inspect CLI dependencies, provider CLI versions/capability hints, CDX_HOME permissions, missing state, orphan profiles, and pending quarantines; optionally filter issue severities. `--check-provider-flags` additionally verifies that the CLI flags cdx maps for each permission are actually accepted by each provider's installed CLI |
| `cdx repair [--dry-run] [--force] [--json]` | Plan or apply safe repairs for missing state files, quarantines, and orphan profiles |
| `cdx view [--json] [--lan] [--lan-rw] [--focus <ref>] [--read] [--port <port>] [--host <host>] [--refresh-interval <s>] [--tls] [--tls-cert <path>] [--tls-key <path>] [--open] [--no-open]` | Open the Logics browser/focus viewer by delegating to `logics-manager view`; all viewer flags are forwarded; JSON mode reports diagnostics without launching it |
| `cdx update [--check] [--yes] [--json] [--version TAG]` | Update cdx-manager using the installer that matches how it was installed |
| `cdx update all [--yes] [--json]` | Check installed providers, RTK, and Ponytail across Codex profiles; show the plan and ask once before applying supported native/Homebrew updates and missing RTK/Ponytail setup |
| `cdx ready [--refresh] [--json]` | Schedule an OS notification for the next cooling-down assistant that becomes ready, then return immediately |
| `cdx notify` | Internal provider hook target for agent alerts and agent state; use `cdx set <name> --notify on` or `--agent-state on` to enable it |
| `cdx agents [--max-age-hours N] [--json]` | Each session's last known agent state (working, waiting, done, failed, limit, ended), waiting first; records older than N hours (default 24) are dropped. See [Agent state](sessions-and-notifications.md#agent-state) |
| `cdx next [--json] [--refresh]` | Select the best next assistant using the same priority logic as `cdx status` |
| `cdx select --provider PROVIDER [--min-reasoning-effort minimal\|low\|medium\|high\|xhigh] [--min-power minimal\|low\|medium\|high\|xhigh] [--require-ready] [--refresh] --json` | Select a suitable session for headless automation |
| `cdx run [session] --cwd PATH (--prompt-file PATH\|--prompt TEXT\|--prompt-file -) [--provider PROVIDER] [--model MODEL] [--kind assistant\|code-review\|retro] [--reasoning-effort minimal\|low\|medium\|high\|xhigh] [--power minimal\|low\|medium\|high\|xhigh] [--permission MODE] [--timeout-seconds N] [--budget USD] [--extra-args 'ARGS'] [--label TEXT] [--max-parallel N] [--continue-run RUN_ID] [--detach] [--failover] [--refresh] --json` | Run one headless task and return a stable JSON result; `--detach` returns the `run_id` at launch without waiting, `--failover` continues the task on the next account when this one hits its rate limit (with `--detach` too: the detached cdx child applies it and the run's `occupancies` record each move), `--prompt-file -` reads the prompt from stdin, `--label` names the run in `cdx runs`, `--max-parallel N` (default `CDX_MAX_RUNS`; unset, invalid, 0 or negative means no limit) refuses to start with `too_many_runs` when N runs are already running, `--kind` (default `assistant`) labels the run record and `code-review` adds a review report to its final payload |
| `cdx run-report <run_id> --json` | Full report, transcript metadata, and final payload for a run; `final_message` is the run's last assistant message, read from Claude's `result` envelope or Codex's last `agent_message` (null when neither exists) |
| `cdx run-status <run_id> --json` | Status of one run by id |
| `cdx run-tail <run_id> [--lines N] --json` | Last lines of a run's own output, while it is still running or after it finished |
| `cdx runs [--limit N] [--since 7d\|today\|DATE] [--running] --json` | List recent runs; `--since` returns every run completed after the cursor and ignores `--limit`; `--running` returns every run still running, uncapped. A run's `kind` is one of the values `cdx schema --json` lists under `enums.kind` |
| `cdx schema --json` | Publish the enums, mutually-exclusive argument groups, and error codes programmatic callers should validate against |
| `cdx stats [name] [--since 7d\|today\|DATE] [--from DATE] [--to DATE] [--by session\|project\|model] [--json]` | Aggregate launch counts, duration, and known token usage by session, for headless and interactive runs alike. `--by project` groups runs by the recorded canonical source repository (labelled by the shortest distinguishing path suffix; `project` in JSON holds the canonical identity, `session_name` the display label, and `-` explicitly means unknown), `--by model` by the model that served them (same totals, same pricing; default `session`). PROV. lists every provider a row saw, such as `claude+codex`. Without a session filter it also prints what rtk saved over the period (`rtk` in JSON), read with `rtk gain` from `RTK_DB_PATH` when set, else the shared history, and the older per-profile ones. |
| `cdx status [--json] [--refresh\|--cached] [--timeout SECONDS]` | Show token usage table for all sessions; empty credits, block, and reset columns are omitted; `--cached` skips live provider probes and returns only stored status; Claude rows also report the auth type (`setup-token` or `full-login`) in a TYPE column and as `auth_type` in JSON. |
| `cdx status --small [--refresh\|--cached] [--timeout SECONDS]` / `cdx status -s [--refresh\|--cached] [--timeout SECONDS]` | Show compact token usage table without provider, blocking quota, credits, and updated columns |
| `cdx status <name> [--json] [--refresh\|--cached] [--timeout SECONDS]` | Show detailed usage breakdown for one session; `--cached` avoids live provider refreshes |
| `cdx tray status [--json] [--refresh] [--beat]` | Emit the tray snapshot: one icon state, one line per enabled session, and how fresh each figure is. Reads stored status by default; `--refresh` is the only path that probes a provider; `--beat` also records a heartbeat, as `cdx tray heartbeat` does, which is how a companion claims alert delivery |
| `cdx tray launch [--json]` | Start the installed tray companion, detached. Reports `tray_companion_not_installed` when nothing is recorded, or `tray_companion_missing` when the recorded companion is gone. `CDX_TRAY_BIN` points it at a locally built one |
| `cdx tray install [--json] [--yes] [--autostart\|--no-autostart] [--alerts\|--no-alerts]` | Download the companion for this OS and architecture, verify its published checksum before unpacking, record what was written, and start it. It asks whether to launch at login; provider-hook consent is requested separately at the first eligible interactive session launch. Refuses when no checksum is published for the asset |
| `cdx tray uninstall [--json]` | Remove exactly what `install` recorded, and nothing else |
| — | `cdx update` also moves an installed companion to the new release, and says so. A companion already running keeps executing the build it started with, so it reports that too rather than leaving you to wonder why the menu looks unchanged |
| `cdx tray autostart [on\|off\|status] [--json]` | Start the companion at login, or stop doing so. Off until asked, idempotent, and the state is read back from the platform rather than from what CDX last intended |
| `cdx tray events [--json]` | List agent alerts a running companion has not shown yet. The companion reads these instead of the spool file, so a Windows tray can collect events from CDX in WSL over the same interop it already uses |
| `cdx tray ack <id>... [--json]` | Mark events as shown, idempotently |
| `cdx tray heartbeat [--json]` | Record that a companion is alive. `cdx notify` publishes to the tray only while this is fresh, and delivers directly otherwise |
| `cdx tray terminal [status\|list\|set <app>\|clear] [--json]` | Choose which terminal a tray session row opens; the tray exposes the same candidates plus **System default**. `cdx tray terminal list` reports candidates and the stored choice, and `clear` returns to the platform default. The value is an application name, never a command. A named terminal that disappears is reported unavailable and never silently replaced by another terminal. |
| `cdx tray sort [status\|set <capacity\|reset\|recent>] [--json]` | Persist the tray session order: current capacity-first order, nearest reset first, or most recently launched first. This affects only the tray menu, never `cdx next` or automatic session selection. |
| `cdx tray plugin [status\|enable <name>\|disable <name>\|run <action>] [--json]` | Turn a tray integration on or off, and list what is enabled. Opt-in in both directions and reversible; nothing enables one implicitly. `logics` is the only one that exists, and `status` says once when it is installed but not enabled. `run` is what the tray calls back with a card's action id and is not meant to be typed |
| `cdx tray alerts [on\|off\|status] [--json]` | Silence agent alerts, or let them through again. These commands work with or without a running tray: with one, muted events remain in its menu; without one, delivery falls back directly to the desktop notification channel. In both cases `off` suppresses banners and `on` restores delivery for the next event, including hooks already running with an older launch environment. Distinct from provider-hook consent, which controls configuration writes |
| `cdx tray doctor [--json]` | Report companion, executable, version, running instance, autostart, and the two capabilities that fail silently — whether this desktop can draw a tray icon at all, and on Windows whether the Start Menu shortcut toasts depend on exists. Reads only; it never repairs |
| `cdx --help` | Show usage |
| `cdx --version` | Show version |

`cdx sessions --json` preserves its existing per-profile rows and fields, including
its recorded wrapper `pid`, launch `cwd`, and saved `conversation_id`. Each row
also contains `processes`, one entry per running agent attributable to that
profile. On Linux, this bounded, best-effort scan checks at most 8192 `/proc`
entries, reads at most 256 KiB per process file (16 KiB per Claude session file),
and follows at most 16 same-user ancestors to find a `script` wrapper. Only
processes owned by the current user are inspected; unreadable, exited, ambiguous
or unmatched processes are skipped. Profile attribution uses the provider and
its `HOME`, `CODEX_HOME`, or profile `CLAUDE_CONFIG_DIR`, not a workspace guess.
Other platforms return an empty list. `--all` retains its existing idle-profile
behavior; discovery does not add or remove profile rows.

Each process exposes `agent_pid`, nullable `wrapper_pid`, `provider`, nullable
`conversation_id`, `conversation_source`, nullable `launch_conversation_id`,
`cwd` (the live `/proc/<agent_pid>/cwd` link), and `started_at` (UTC ISO timestamp
from kernel process timing, or null). Claude's current ID comes from `sessionId`
in `<CLAUDE_CONFIG_DIR>/sessions/<agent_pid>.json`, defaulting to
`<HOME>/.claude/sessions/<agent_pid>.json`, and is reread on each call so `/clear`
is reflected. `conversation_source` is `claude_session_file` on success;
`claude_session_file_missing`, `claude_session_file_invalid`,
`claude_session_file_unavailable`, or `claude_config_dir_unavailable` explains a
null ID. The separate launch ID comes only from that Claude process's explicit
`--session-id` or `--resume` argument. Codex, Antigravity and Ollama currently
report null conversation and launch IDs with
`conversation_source: "current_conversation_unavailable"`; no saved ID or recent
transcript is treated as proof of a process's current conversation. Missing cwd
links yield null. `cdx schema --json` advertises the item fields under
`outputs.sessions.processes`.

---

### Tray snapshot

`cdx tray status --json` is the contract an optional desktop tray companion reads. It adds nothing to the quota pipeline: it interprets the status CDX already stores.

- **Cached by default.** A tray polls, and a live provider probe serializes on the Codex auth lock, which the launcher holds for a whole interactive session. Polling it would be locked out at best and race a rotating OAuth refresh token at worst. Only `--refresh`, a deliberate user gesture, probes.
- **Freshness is a value, not an error.** Each session reports `fresh`, `stale`, `auth_locked`, or `unknown`. `auth_locked` means a session is running and its quota cannot be refreshed until it exits — pressing refresh will not help, and the snapshot says so instead of ageing silently.
- **The icon leaks nothing.** `icon` holds a state, a reason, and a count. Session names, providers, and figures live in `sessions`, which a companion shows only once the user opens the menu.
- **Versions drift on purpose.** The payload carries `schema.major`. A reader meeting a newer major keeps every field it understands and surfaces one update hint, so upgrading CDX never breaks an installed companion.

```json
{
  "schema": { "name": "cdx.tray.snapshot", "major": 1, "minor": 0 },
  "icon": { "state": "low", "reason": "fresh", "session_count": 2 },
  "sessions": [
    { "name": "work", "provider": "codex", "available_pct": 18, "state": "low", "freshness": "fresh", "reset_at": "..." }
  ],
  "refreshable": true,
  "actions": ["refresh", "open_terminal"]
}
```

Icon states are `ok` at 25% remaining and above, `low` below 25%, `critical` below 5%, and `unknown` when nothing was ever reported. The closed icon shows the most urgent session, and a session that never reported never outranks one with real news.

### Setup hints

`cdx` and `cdx status` may end with one dim line pointing at an optional surface you have not set up yet — the tray companion, or agent alerts. They exist because neither is discoverable from the output of the commands you already run.

They are deliberately hard to become noise. One hint per invocation at most, not again for six hours, and each one retires for good after three showings: if you saw it three times and did not act, that is an answer. A hint never appears in `--json`, never appears alongside an update notice, and is answered entirely from local state — nothing here probes a provider or the network. `CDX_NO_HINTS=1` turns them off outright.

### Tray companion: what vouches for it

The companion is a native binary distributed as a release asset, not part of the pip package. Its trust model is worth stating plainly rather than leaving you to assume the usual one.

- **Where the checksum comes from.** Releases older than the one you are running are vouched for by `checksums/release-archives.json`, committed to the repository before those assets existed. Your own release is a special case: its tray assets are built after the tag, so no package built at tag time can carry their checksums. For that one version CDX reads the ledger the release publishes beside the assets — the publisher's own assertion over the same channel, which catches a truncated download or a wrong-architecture asset but does not defend against someone who can rewrite the release itself.
- **The checksum is the vouching, not Apple or Microsoft.** The macOS bundle is signed with a *self-signed* certificate. That signature exists because Apple Silicon refuses to execute unsigned arm64 code at all — it is not a claim that Apple reviewed anything. What actually vouches for the asset is the SHA-256 published in `checksums/release-archives.json`, verified before a single byte is unpacked. An asset with no published checksum is refused rather than installed hopefully.
- **Tray integrations are cards, not plugins.** `cdx tray plugin enable logics` adds one section to the menu: a blocked/ready summary and at most two rows — the first blocked document, because it is what stops work, and the highest-priority task in progress, because it is what to do instead. Clicking a row opens the Logics viewer focused on it. Tray openings ask Logics for a free local port, so an existing viewer is never displaced.

- **Alert return path.** When an alert originated in iTerm2, the macOS tray row and native CDX notification focus that exact iTerm session. macOS may ask once for CDX to control iTerm; declining leaves the alert visible but does not focus a different window. Script Editor fallback banners and Windows/Linux notifications remain delivery-only.

  There is deliberately no marketplace, no discovery, no installation from a URL, and no plugin auto-update. An adapter is a function in this repository, named in a registry CDX owns, so nothing unknown can run. Adapters produce data and never behaviour: a card is a summary, rows, and action ids from a fixed vocabulary, and the tray hands an id back to CDX rather than running anything itself. Adding a capability is a change to CDX, reviewed like any other.

  A card is built from `logics-manager status --format json` and from nothing else, so nothing about your documents is read or stored. It is refreshed at most once a minute, or on demand from the menu — an integration never pays the tray's polling rate. If `logics-manager` is absent, slow, failing or in a directory that is not a Logics repository, the card is simply not there: an integration cannot degrade the session rows the tray exists to show.

- **Install through `cdx tray install`, and no download link is offered.** This is a security property, not a convenience. A file fetched by CDX carries no macOS quarantine attribute and no Windows Mark-of-the-Web, so nothing puts Gatekeeper or SmartScreen between you and a companion you asked for. The same file fetched through a browser would carry both. That is why no direct download URL is published: it would be a worse path wearing the same clothes.
- **Nothing is silently replaced.** An update downloads, verifies, and *proves the replacement starts* before the working companion is touched. A corrupt asset or one built for the wrong architecture costs an error message, not a tray you can no longer launch. An interrupted update is a named, recoverable state that `cdx tray doctor` reports.
- **Uninstall removes only what install recorded**, from a record CDX wrote itself. A damaged record reads as absent rather than being guessed at, because that record drives deletion.
- **Linux carries no C library.** The Linux asset is statically linked against musl, so there is no glibc version to match and no `gtk`, `libxdo`, or `appindicator` package to install. Tray support is resolved at runtime by looking for the `org.kde.StatusNotifierWatcher` D-Bus name — never by matching a distribution or desktop name. A session without it is told so, and nothing is registered to start at login.
- **Version drift between CDX and the companion is normal**, since pip upgrades one and `cdx tray install` the other. Whichever is older keeps serving every field it understands and shows one update hint.
- **About stays actionable.** The last tray action before Quit is `About (v<installed CDX version>)`; it opens the project’s GitHub page with the platform’s normal browser launcher.

## JSON Output

`cdx-manager` can be consumed by other apps through its CLI JSON contract.

Commands with machine-readable output:

- `cdx --json`
- `cdx status --json`
- `cdx status <name> --json`
- `cdx add ... --json`
- `cdx cp ... --json`
- `cdx ren ... --json`
- `cdx label ... --json`
- `cdx rmv ... --json`
- `cdx clean ... --json`
- `cdx disk ... --json`
- `cdx reset ... --json`
- `cdx export ... --json`
- `cdx import ... --json`
- `cdx login ... --json`
- `cdx logout ... --json`
- `cdx disable ... --json`
- `cdx enable ... --json`
- `cdx context ... --json`
- `cdx memory ... --json`
- `cdx handoff ... --json`
- `cdx history ... --json`
- `cdx stats ... --json`
- `cdx last --json`
- `cdx doctor --json`
- `cdx repair --json`
- `cdx view --json`
- `cdx update --json`
- `cdx ready --json`
- `cdx select ... --json`
- `cdx run ... --json`

Status rows also carry `runs_out_at_iso`: when the account empties if it keeps the pace it has used since its 5-hour or weekly window opened (the earlier of the two), or `null` when that pace lasts until the reset. `cdx status <name>` shows it as `Runs out: ~11:48 at this pace`. It is an average since the window opened, not a prediction of what you will do next.

Status rows also carry `rate_limit_reached`: the provider's typed block reason (Codex, for example `workspace_owner_credits_depleted`), or `null`. A row with a reason is never selected by `cdx run` and confirms exhaustion for `--failover`, even when its percentages still read healthy.

In `cdx status --json` rows, `reset_5h_at`, `reset_week_at` and `reset_at` are display strings in local time with no year (`Oct 20 15:00`). Read `reset_5h_at_iso`, `reset_week_at_iso` and `reset_at_iso` instead: ISO 8601 with the local offset, or a bare date when the provider gave no time of day.

Success payloads follow a shared envelope:

```json
{
  "schema_version": 1,
  "ok": true,
  "action": "add",
  "message": "Created session work (codex)",
  "warnings": [],
  "session": {
    "name": "work"
  }
}
```

Most commands use a shared stderr JSON envelope for errors whenever `--json` is present:

```json
{
  "schema_version": 1,
  "ok": false,
  "error": {
    "code": "invalid_usage",
    "message": "Usage: cdx status [--json] [--refresh|--cached] [--timeout SECONDS] | ...",
    "exit_code": 1
  }
}
```

`status --json` and similar commands also use the same envelope and place non-fatal issues in `warnings` instead of mixing plain-text diagnostics into `stderr`. `cdx run --json` is the exception: it always writes one final JSON payload to stdout, including cdx-side and provider-start errors, so supervisors can parse a single result stream while provider stdout and stderr are captured to files.

This makes `cdx-manager` usable from editor plugins, scripts, and desktop apps without scraping human-readable terminal output.

### Headless Runs

`cdx run` is designed for supervisors such as Orchestia. In `--json` mode, stdout contains only the final JSON payload; provider stdout and stderr are captured to files.

```bash
cdx run codex-work \
  --cwd /path/to/workspace \
  --prompt-file task_prompt.md \
  --model gpt-5.3-codex \
  --reasoning-effort low \
  --permission workspace-write \
  --timeout-seconds 1800 \
  --json
```

Use provider-based auto-selection when the caller wants cdx-manager to pick the account:

```bash
cdx run \
  --provider codex \
  --cwd /path/to/workspace \
  --prompt "Summarize the repo status." \
  --reasoning-effort low \
  --json
```

The result includes `launcher: "cdx"`, `run_id`, selected `session`, `provider`, `exit_code`, `duration_seconds`, absolute `transcript_path`, `stdout_path`, `stderr_path`, and normalized usage token fields. Codex headless runs use `codex exec --json`; Claude headless runs use `claude --print --output-format json`. Token counts are `null` when the provider does not expose a supported JSON or JSONL usage shape.

Remote Claude profiles require a dedicated long-lived token produced by `claude setup-token`
on the launching host. Supply only that token on standard input to
`cdx auth claude-token <profile>` (never put it in command arguments). This stores
`.cdx-remote-claude-token` with mode `0600` in the controller profile; ordinary
interactive Claude credentials and ambient API keys are not a fallback. A missing
or unsafe file stops before SSH and names this command.

Run `cdx run <profile> --remote worker --cwd /srv/project --prompt-file task.md --json`.
Claude always uses bubblewrap isolation, even without `--isolate-workspace`, and
requires matching Claude CLI versions on the controller and Linux worker, Python 3,
bubblewrap, pasta, nftables, working namespaces and memory-backed `/dev/shm`.
No worker login or profile mount is needed. Each attempt sends the token over SSH
stdin, then a private pipe through the sandbox to an exec shim that sets it only
in Claude's environment. It is never a worker credential file or command argument;
provider output is redacted before persistence. Fresh volatile HOME storage holds
`.claude`, `.claude.json`, caches and traces and is removed on exit, failure or stop.
`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` and
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` remain set; API keys, proxy tokens,
proxy URLs and cloud-provider variables are excluded from the sandbox environment.
`--bare` is refused because it ignores OAuth. The outer sandbox owns tool permissions,
including a read-only checkout for `--permission review`.

Without `--network-access`, the trusted setup resolves `api.anthropic.com` and allows
HTTPS to those addresses plus public DNS, with other external destinations dropped.
`--network-access` retains the existing public tool-network policy. Address resolution
is fixed for the attempt; restart a run if the inference service changes addresses.
Usage and observed models come from Claude's JSON result. Fresh runs are required;
remote `--continue-run` remains unsupported.

Remote Antigravity profiles use the worker's existing login, created once by the
operator in that worker user's normal HOME. Run
`cdx run agy-profile --remote worker --cwd /srv/project --prompt-file task.md --json`.
Matching `agy` versions are required on both hosts. Bubblewrap is mandatory;
each attempt has a memory-backed HOME and mounts only the worker's mode-600
`.gemini/antigravity-cli/antigravity-oauth-token` authentication file, read-only.
The installation is read-only. No token is copied into the volatile HOME or sent
to the controller. A worker token lock excludes concurrent cdx attempts;
independent native agy launches must be kept out of the same worker account slot.
`AGY_CLI_DISABLE_AUTO_UPDATE=true` is set. Runs use `-p --output-format json`,
with closed stdin, and require JSON status `SUCCESS` without refused actions.
Missing login and expired-session errors require operator login on the worker;
cdx does not launch an authentication command. Usage is read from the JSON result.

The conservative HTTPS candidate list is `oauth2.googleapis.com`,
`cloudcode-pa.googleapis.com` and `daily-cloudcode-pa.googleapis.com`, resolved
on the worker before isolation, plus DNS to `1.1.1.1`/`9.9.9.9`. Other public
traffic is dropped even with `--network-access`; private ranges remain denied.
This list has **not** been accepted against live inference in the mission sandbox.
The token remains read-only pending a measured receipt showing whether refresh
writes it in place. See
`logics/runbook/fragments/2026-11-03-antigravity-44674fc58c.md` for evidence and
the host measurement command. Local Antigravity headless runs retain their profile HOME
and credentials; the worker login, token lock and volatile HOME policy apply only
to remote runs.

Remote Ollama profiles use the worker's unauthenticated HTTP API at
`127.0.0.1:11434`, with `/api/show` followed by `/api/chat` (`stream: false`).
Use `cdx run local --remote worker --cwd /srv/project --model qwen3:8b --prompt-file question.txt --isolate-workspace --json`.
The prompt file is read on the launching host; the model must already exist on
the worker. This is text generation only, not an autonomous coding agent, and
it does not edit the repository. The result includes `execution_mode`, an
`execution_note`, generated text in `result`, and `prompt_eval_count` / `eval_count`
alongside normalized `usage` counters. Missing models and unreachable APIs fail
without pulling models or authenticating. Isolated clients use a private Unix
socket relay restricted to capability and non-streaming inference calls for the
selected model, with a read-only checkout and no network or model-file mounts.
`--network-access` does not enable networking for this text-only client.

Known headless and completed interactive token usage is persisted in launch history and can be aggregated later. Interactive records are best-effort local data: Codex reads its latest cumulative rollout snapshot, Claude reads its assistant usage records, and Ollama — which writes no transcript of its own — is launched with `--verbose` so its per-response token counts land in the terminal capture cdx already takes. Antigravity reports no usage: its history is schema-less binary protobuf and its logs carry no usage line, so those sessions show no tokens by nature rather than by omission.

`--continue-run RUN_ID` resumes the exact provider conversation from a finished Claude or Codex run, inferring its profile and pinning its recorded model and effort. Existing targets and settings may be supplied only if they match. The parent transcript must still exist. `parent_run_id` links the new run to its parent in run results, the registry, and history; `conversation_id` identifies the provider conversation. Detached continuations preserve these settings through the cdx supervisor. Codex continuation usage is measured between exact transcript snapshots before and after the run, since exec resume can report conversation totals. If either boundary is unavailable, per-run usage stays unknown with `usage_attribution: "continuation_usage_unavailable"` in history instead of counting earlier turns again. Continuation does not use automatic capacity recovery or model fallback, and cannot be combined with `--failover`.

For Claude continuations, profile and per-run `--extra-args` may include `--settings VALUE` or `--settings=VALUE` only when VALUE is an inline JSON object or a readable UTF-8 JSON file containing only the top-level key `permissions` (an empty object is also accepted). For example, `--extra-args '--settings /path/to/permissions.json'` retains an explicit tool allowlist. Validated content is copied atomically to an owner-only settings file (mode 0600) in private run state beside the run artifacts. Claude receives this path, so subsequent source file changes cannot alter the launch and large permissions lists do not expand the launch arguments. The copy is retained with the run state and removed with that state; isolated continuations mount only this settings file read-only. All other keys, including `model`, `effortLevel`, `env`, `hooks`, `apiKeyHelper`, and fallback settings, are refused with `continue_run_settings_mismatch` and the refused key names. Unreadable files, invalid JSON, and non-object values return the same error code. Other model, effort, agent, and conversation overrides remain refused.

Use repeatable `--ro-input NAME=PATH` with `--isolate-workspace` to expose additional directories read-only:

```bash
cdx run work --cwd /tmp/example-worktree --prompt 'Read the input' --isolate-workspace --ro-input EXAMPLE_ROOT=/tmp/example-input --json
```

Each input appears at `/opt/inputs/<name in lowercase>` in the sandbox, and the provider receives `NAME` set to that path (for example, `EXAMPLE_ROOT=/opt/inputs/example_root`). Repeat the option with distinct names for multiple inputs. Names must match `[A-Z][A-Z0-9_]*`; cdx-managed and provider credential variables are reserved. Duplicate names are refused. Inputs are read-only even when the workspace is writable.

The source must be an existing directory owned by the execution user. Top-level symlinks are refused. Paths inside or containing the worktree, home configuration directories, cdx state, or credential locations are refused. Internal symlinks are preserved and resolve only against paths visible inside the sandbox; cdx does not mount their host targets. Validation failures stop the run. For remote isolation, use absolute paths on the worker; validation also runs there before execution.

Inputs are persisted with the run. `--continue-run` automatically reapplies and revalidates the parent's inputs; an explicit input list must match the parent. Removed, unsafe or newly overlapping directories stop continuation. Detached launches preserve the same input list. `cdx schema --json` advertises `capabilities.ro_inputs = 1`.

A local parent started with `--isolate-workspace` automatically resumes inside isolation; repeating `--isolate-workspace` is accepted. Supply the same `--cwd`. The parent's network setting and workspace mount permission are inherited, even if the profile settings changed. A different cwd, permission, or enabling network access on an offline parent is refused. Isolation is never removed on resume. Conversation transcripts are persisted under `CDX_HOME/isolated-runs/RUN_ID/` and mounted into the otherwise fresh provider home; host profile credentials and configuration are not mounted. Chained and detached continuations reuse that same transcript storage. Removing the workspace or its conversation storage makes continuation unavailable; replacing the recorded workspace directory is also refused. Older isolated runs whose ephemeral transcripts were not retained must start fresh. Remote continuation remains unsupported.

Continuation errors are `continue_run_workspace_gone` (missing or replaced isolated workspace, or missing retained conversation storage), `continue_run_not_found` (unknown parent), `continue_run_mismatch` (another or missing profile/provider), `continue_run_unavailable` (unfinished or unsupported run, expired transcript, or unavailable settings), and `continue_run_settings_mismatch` (changed model/effort or incompatible flags). Callers may start a normal run after a refusal by omitting `--continue-run`.

#### Run budgets

`cdx run --budget USD` accepts a finite positive amount in US dollars. It uses the same token pricing function, cache rates, and `CDX_TOKEN_PRICES` overrides as `cdx stats`. The supervisor checks reported stdout usage and the exact provider conversation transcript every 250 ms while waiting, and checks again at completion. Claude's transcript messages are summed; continuation measurements subtract the transcript snapshot taken before this run. Earlier turns do not consume the new budget. Measured costs from retries, model recovery, and account failover share the same run budget.

At or above the limit, cdx terminates the provider process tree, skips further recovery/failover, records the run as `failed`, and exits with **125**. The final JSON has `ok: false`, `exit_code: 125`, `error.source: "cdx"`, `error.code: "budget_exceeded"`, and `error.spent_usd` with the measured estimated spend across attempts. `cost_usd` repeats that amount and `budget_usd` records the requested limit. Normal results also include nullable `cost_usd` for their observed usage and `budget_usd` (`null` without the flag).

With `--detach`, the launch still exits successfully and includes `budget_usd`; cdx always uses its own child supervisor for budgeted runs, including when native background delegation is enabled. Inspect `cdx run-status RUN_ID --json` or `cdx run-report RUN_ID --json` for the child's final payload and budget error. `--continue-run` starts a fresh budget for the new run, including in detached mode.

Conservative assumption: this is a stop based on observed, priceable usage, not a prepaid billing limit. Provider updates can arrive late or only at completion, and termination can take time, so actual spend can exceed the amount. Before the first measurement, `budget_status` is `usage_not_measured`; absence is not zero spend. Once usage is measured, missing continuation boundaries, mixed/unobserved models, and unknown prices stop further execution/recovery with exit **125**, `error.source: "cdx"`, `error.code: "budget_unverifiable"`, `budget_status: "unverifiable"`, and `cost_usd: null`. This is a measurement failure, not a claim that the dollar limit was exceeded or enforced. This fail-closed guarantee also applies to a remote agent that has already completed: the supervisor reports `failed`/125 while retaining its final output and artifacts. Without `--budget`, unknown pricing does not replace the provider's completion status. Supply a `CDX_TOKEN_PRICES` override for a model missing from the table. Existing profile-level `cdx set --budget` settings remain the provider-native Claude cap and apply independently.

Every usage record, whichever path produced it, uses one set of definitions:

| Field | Meaning |
| --- | --- |
| `input_tokens` | Uncached input **only**. Codex reports a cache-inclusive count natively; cdx reduces it to the remainder so the field means the same thing on every provider. |
| `cache_creation_tokens` | Tokens written to the provider's prompt cache. |
| `cache_creation_1h_tokens` | The part of `cache_creation_tokens` written with Anthropic's one-hour TTL (`cache_creation.ephemeral_1h_input_tokens`), which costs 2x instead of 1.25x. A subset, never added to a total; `null` when the provider does not report the split. |
| `cache_read_tokens` | Tokens served from it. Kept apart from cache creation because the two cost roughly 1.25x and 0.1x of uncached input, a difference no summed figure can recover. |
| `cached_input_tokens` | `cache_creation_tokens + cache_read_tokens`, derived. The single CACHE column in `cdx stats` shows this. |
| `output_tokens` | Generated tokens. |
| `cache_hit_ratio` | Cache reads divided by uncached input plus cache writes plus cache reads, excluding output. A fraction from 0 to 1; `null` without a reported read split or with zero input. When Codex omits writes, its reported total input is uncached input plus reads. |
| `reasoning_tokens` | Reasoning the provider counts separately. Codex reports one; Claude does not, because it bills thinking as output — those tokens are already inside `output_tokens`, so an empty REASON column for Claude is correct rather than missing. |
| `total_tokens` | `input + cache_creation + cache_read + output`. Cache is typically the bulk of real consumption, so a total that left it out would not be slightly low — it would be a different quantity. |

Cached input is counted once: it is excluded from `input_tokens` and reported in the cache fields, never in both. `null` means the provider did not report the figure, which is not the same as zero.

History and stats text show `cache 72 %` beside tokens, or `cache n/d` for unknown splits. Stats JSON adds `cache_usage` with nullable sums for `input_tokens`, `cache_creation_tokens`, `cache_read_tokens`, and `output_tokens`. Existing numeric aggregate fields are unchanged. `cache_hit_ratio` is computed from summed reads and input across measured runs, never by averaging percentages. `measured_runs`, `measured_input_tokens`, and `measured_cache_read_tokens` describe ratio coverage, excluding missing splits and zero-input runs. Each session, project, model, and total includes `run_types.cold` and `run_types.continued`, each with `runs` and the same cache summary fields. A missing `parent_run_id` counts as cold for historical compatibility.

`cdx stats` also shows a **`COST~`** column and ranks sessions by it. It weights each token class by what it costs relative to one uncached input token — cache read at the recorded model's ratio (0.1x by default), cache write 1.25x (2x for one-hour writes), and output at the recorded model's output/input ratio — and reports the result in uncached-input-equivalent tokens. These are ratios rather than prices. It is **not** a currency amount, and it is not comparable across providers whose own prices differ. Writes reported as one-hour are weighted 2x; a record without that split keeps the five-minute 1.25x rate.

Ranking on the raw total would put a session that mostly replayed a cache above one that spent far more on generation, because cache reads are typically the overwhelming majority of tokens consumed while costing a fiftieth of an output token.

`cdx history --json` includes `cost_usd` on every entry, calculated when read using the current stats price table and overrides. Missing or untrusted usage and unknown serving models/prices yield `null`, never a fabricated zero. Cache reads, writes (including one-hour TTL), and output use the same rates as stats.

The **`USD~`** column turns that into money for runs whose serving model cdx recorded. It prices each token class directly using the built-in model table. To customize prices: set `CDX_TOKEN_PRICES` to a JSON object mapping model id to dollars per million tokens to override the built-in table, whose last review date is printed with the totals. A run whose model cdx never saw stays unpriced rather than being charged at a default tier, and the totals line says how many runs were actually priced.

The table requires `input` and `output` prices in USD per million tokens and accepts an optional `cache_read` price in the same units. Without it, cache reads cost 0.1x input; cache writes assume 1.25x input. GPT-6.1 Sol and Claude Opus 5.5 use 0.05x cache reads, while Claude Fable/Mythos 5.1 use 0.025x. Both `COST~` and `USD~` honor those rates. `CDX_TOKEN_PRICES` replaces the supplied model row: a two-field override keeps the legacy 0.1x fallback; include `cache_read` to override it (including zero).

Override rates must be finite and nonnegative. A zero input rate can still yield `USD~`, but ratios relative to input are undefined; `COST~` then shows `-` for an uncovered session. JSON keeps the numeric `weighted_tokens` sum for covered runs and reports `weighted_runs` and `unweighted_runs` so partial coverage is visible.

The figure uses standard public list prices, excluding Fast/priority, Batch/Flex, regional premiums, and tool fees — not an invoice. When a run changes models without a measured per-model token split, its USD estimate is unavailable rather than assigning all tokens to one model. OpenAI's long-context tier, which increases rates above a 272K-token request, is **not** modelled: cdx records tokens per run rather than per request, so it cannot tell which requests crossed that line, and long-context Codex work is under-costed.

`cdx stats` counts completed history attempts. A headless failover has one logical run in `cdx runs` but one history row per attempted session, including failed attempts that reported usage. Period filtering includes the entire run in every period it overlaps, so adjacent daily results can both include a run crossing midnight; adding daily totals may exceed a combined period. JSON `accounting` names this policy and the current price-table source. `usage_runs` and `priced_runs` show how much of the token total has a dollar estimate. Live runs are absent until their history row is written, and unknown usage is different from measured zero.

Completed results, registry records, and history JSON include `cost_status` (`estimated` or `unknown`) and nullable `cost_reason`: `usage_not_measured`, `model_not_observed`, `model_price_unknown`, `attempt_usage_unavailable`, or `mixed_models_without_counters`. Stats include `unpriced_reasons` counts alongside `priced_runs` and `unpriced_models`. These are list-price estimates, not billing receipts. `budget_status` is `not_requested`, `usage_not_measured`, `estimated`, `exceeded`, or `unverifiable`.

New headless attempts have distinct `attempt_id` values and artifact paths, including retries on the same profile. Final payloads and registry reports expose `attempts` with their individual model evidence, counters, and estimates; top-level usage describes the final attempt, while a budget-exceeded spend includes all attempts. New isolated Codex attempts mount only a fresh sessions directory from volatile `/dev/shm` storage. The supervisor reads the exact `thread.started` rollout while it exists and at closeout, requiring matching session identity, turn timestamps within this attempt, and token counters consistent with stdout. It exports `usage_evidence` containing only the stdout attempt identity, thread id, timestamp bounds, turn ids, observed models, and normalized counters; live rollout counters can establish the first measurement before `turn.completed`. No requested model, agent-authored cost report, current profile setting, prompt, message, or tool output is used as model evidence. The raw temporary sessions are removed at closeout, including cancellation and startup failure; they are never copied into persistent run artifacts. Host profiles are not mounted. Remote Codex runs ship the same observation reader and normalization code over the existing stdin bootstrap. The worker validates the exact fresh-home thread, timestamp bounds and matching counters with the local 128 MiB limit, and returns only normalized evidence through supervisor frames, separate from provider stdout. The controller attaches its own stdout path, run id and attempt id before live budget checks and final persistence; it never consults a controller profile rollout for remote usage. Worker stdout capture stays in the existing volatile private home and is deleted with it. Credentials, refresh handling and workspace mounts are unchanged. Live rollout counters can establish remote usage before `turn.completed`. Mixed serving models stay unpriced without attributable counters. Isolated continuation without comparable launch boundaries stays unmeasured rather than charging an older conversation to the new attempt.

Completed run JSON and registry reports expose `usage_model` separately from the requested `model`. Pricing uses the observed model from provider output; Codex can also supply it through the exact rollout identified by `thread.started.thread_id`. Configured defaults alone never establish serving-model identity, and missing or mixed model evidence stays unpriced. `--by model` groups Claude's `[1m]` context variant with its base model while preserving the original model string and per-run pricing. New runs record this evidence automatically. To recover missing models in existing history, run:

```bash
cdx history backfill-models                  # Preview only (the default)
cdx history backfill-models --dry-run --json # Machine-readable preview
cdx history backfill-models --apply          # Save proven models with a backup
```

The command considers only history rows with usage and an empty or placeholder `usage_model`. Evidence is checked in order: a supervisor-preserved isolated observation tied to the exact stdout attempt and counters, the row's preserved JSON/JSONL stdout, a preserved run-registry report with the same run id, profile, provider and stdout path, then the exact Codex thread rollout or Claude session transcript. Thread/session ids must come from the row or its stdout, or from a preserved transcript path recorded as an exact conversation-id match. The current profile is used only to locate an exact transcript under its auth home; its configured model and latest conversation/transcript never establish a historical model. The requested `model` in a report is also ignored.

Run recovery in dry-run mode first and review every evidence kind and unknown reason before applying. A missing isolated rollout with no preserved observation cannot be reconstructed from a current profile: its historical model and cost remain unknown. No historical recovery is applied automatically. Only one serving model is accepted. Claude `[1m]` variants count as the same model for this check and for stats grouping; the observed spelling is preserved. Mixed models, incomplete turn models, malformed or oversized evidence, conflicting identities and missing exact transcripts stay unknown. For resumed conversations, the conservative rule is that all recorded turns in the exact transcript must agree: this command does not infer historical turn boundaries. Ambiguous higher-priority evidence stops recovery rather than being overridden by a lower-priority source. Missing files may fall through to the next source.

Text and JSON output include counts by evidence kind, counts of unknown reasons and up to 20 samples. Dry-run leaves history and run reports unchanged. `--apply` changes only missing models and their evidence annotation, preserving token counts and unrelated history bytes. It holds the history lock, saves the original bytes to a unique `state/launch_history.jsonl.models-<id>.bak` file, then atomically replaces history. The backup path is printed; a repeated apply leaves already recovered rows alone. `--apply` and `--dry-run` cannot be combined. Subsequent `cdx stats` calls price recovered models when the local price table knows them; unknown models remain unpriced.

The built-in price table ships with **cdx-manager**. Run `cdx update` to receive new model prices; updating Codex or Claude alone does not refresh it. Then check `cdx --version` and `cdx stats --json`. Existing runs with a recorded model are recalculated using the new table when stats are read. `CDX_TOKEN_PRICES` overrides still take precedence. Maintainers: follow [the model and pricing update runbook](https://github.com/AlexAgo83/cdx-manager/blob/main/logics/runbook/run_005_maintaining_the_token_price_table.md) for source checks, tests, release preparation and installed-version verification.

A model absent from the table stays unpriced rather than being charged a default tier, and the totals line names it — which is exactly the key `CDX_TOKEN_PRICES` wants:

```
Totals: 26 runs, ... ; no price for gpt-6-unreleased)
CDX_TOKEN_PRICES='{"gpt-6-unreleased": {"input": 3, "output": 18}}' cdx stats
```

**Prices are the only part of this that rots on its own.** A test fails once the table has gone 90 days without review, and `scripts/check_token_prices.py` compares it against published pricing — outside the test suite, since a check that needs the network fails for reasons nobody wants in CI. A row it cannot confirm is reported as unverified, never as passing. When it finds a difference, follow [the pricing runbook](https://github.com/AlexAgo83/cdx-manager/blob/main/logics/runbook/run_005_maintaining_the_token_price_table.md) — which also records where each vendor's numbers actually live.

Runs recorded before these definitions existed carry figures that are fictitious rather than imprecise — one real session reported 206.6M cached tokens for a period in which its own conversation consumed 33,608, because the old reader picked whichever transcript had the newest modification time and re-read all of it on every launch. They cannot be recomputed: a run's true usage is the increment its transcript gained while it ran, and nothing recorded that. They are therefore excluded from every total automatically, and the totals line says how many runs that covered — so a period containing only such runs reads as absent rather than as a session that spent nothing. The records themselves are left alone, which keeps them recoverable if the marker ever proves wrong; `cdx repair` clears them from the file for anyone who would rather they were gone:

```
cdx repair --dry-run      # says how many records carry unvouched usage
cdx repair                # drops the figures; runs, durations and timestamps stay
```

Records that *are* vouched for but predate the split — headless runs, and anything recorded between the definition landing and the model being captured — are shown as faithfully as their data allows: they carry no creation/read split and no model, so their cached tokens are read as cache reads for weighting and they stay unpriced. `cdx stats` derives each row's `TOTAL` from the columns it displays, so a row always adds up even while history spans both eras.

```bash
cdx stats --since 7d --json
cdx stats work
```

`cdx select` exposes the same session selection logic directly:

```bash
cdx select --provider codex --min-reasoning-effort low --require-ready --json
```

### How cdx picks a session

`cdx select`, `cdx run --provider`, `cdx next`, the `cdx status` recommendation, and `cdx ready` all use one ranking. They used to use two that disagreed, so the answer depended on which command you asked.

**Candidate filters** exclude sessions before any ordering happens: disabled sessions, logged-out sessions (they cannot serve work), sessions of another provider when one is requested, sessions below a requested `--min-reasoning-effort`, and — when readiness is required — sessions with no availability left.

**Ordering** compares the remaining candidates factor by factor:

1. **Usability** — usable now, then blocked with a known upcoming reset, then reset known, then nothing known.
2. **Priority** — the `--priority` you set with `cdx set <name> --priority 0..100`, highest first.
3. Then, for a session you can use now: **credits** (sessions *without* credits first, so included quota is spent before paid credits), **availability**, **reset time**. For a session you cannot use now the order is **reset time** first, then credits and availability — when you cannot use it, what matters is when it comes back.
4. **Reasoning effort** — the lowest configured effort that still clears any requested floor, leaving stronger sessions free for work that needs them.
5. **Session name**, so the order is deterministic.

`--priority` ranks sessions *within* a usability class, never across one. A high-priority session with no quota left does not outrank a usable one: priority expresses which usable session to prefer, not a way to route work somewhere it will fail.

`cdx select --json` reports `selection_policy` (built from the ranking itself, so it cannot describe an order the code does not apply) and `deciding_factor`/`reason`, naming the factor that actually separated the winner from the runner-up for that call — or reporting that it was the only candidate. Do not treat `selection_policy` as a stable identifier; it changes when the ranking changes, which is the point.

`cdx run --provider` selects from cached status by default. Pass `--refresh` to fetch status first. When a session is auto-selected without any recorded availability, the run payload carries a `session_selected_without_status` warning — that is different from a session known to be low, and on a freshly imported or long-idle set of sessions it is the ordinary case.

### Verifying provider flag mappings

cdx translates each `--permission` value into concrete provider CLI flags. Those mappings are declarations about someone else's CLI, and a provider can drop or rename a flag without cdx noticing — which is exactly what happened with an `--experimental-yolo` flag mapped for ollama that the ollama CLI never had.

`cdx doctor --check-provider-flags` verifies them against the installed provider CLIs:

```bash
cdx doctor --check-provider-flags --json
```

For each configured provider it reports, per permission, whether every mapped flag is accepted. A rejected flag is a `FAIL` naming the provider, the permission, and the flag. A provider whose CLI is not installed, or whose help cannot be read, is a `WARN` — never an `OK`: "could not verify" is precisely the state a stale mapping hides in. A provider that maps no flags at all, such as ollama, reports `OK` with an empty mapping, so having nothing to check is distinguishable from having failed to check.

It is opt-in because it costs one provider CLI invocation per configured provider. When it is not requested, the default `cdx doctor` report says so with a `provider_permission_flags_unchecked` warning rather than omitting it, so a green report never implies the mappings were verified.

### Programmatic Callers

`cdx run` blocks until the provider finishes, which suits a supervisor that can wait. Agents, MCP servers, and watchdogs usually cannot, so the surface below exists specifically for them: launch without waiting, watch progress, react to failures by code, and discover valid values instead of hard-coding them.

**Launch without waiting.** `--detach` returns as soon as the run is registered, with the `run_id` already assigned:

```bash
cdx run work --cwd /path/to/repo --prompt-file task.md --detach --json
```

The payload carries `detached: true`, `run_id`, `pid`, and the artifact paths — but no `exit_code`, `duration_seconds`, or `usage`, since the run has not finished. The detached process is put in its own session, so it survives the launcher exiting, including when cdx was invoked over an SSH command that returns immediately. It transitions its own registry entry to a terminal status, so `cdx runs` and `cdx run-status` stay accurate with nobody supervising.

Authentication is still resolved before the launch returns, so a login problem surfaces synchronously rather than silently in the background.

**Watch a run in progress.** `cdx run-status` reports only running/succeeded/failed; `run-tail` shows what the run is actually doing:

```bash
cdx run-tail <run_id> --lines 50 --json
```

It returns the last lines of the run's own `stdout_path` plus its current status, whether the run is still going or already finished. Lines are raw provider output, not summarized. Undecodable bytes come back with replacement characters rather than failing the call.

**Pipe an untrusted prompt.** `--prompt-file -` reads the prompt from standard input, so arbitrary text never has to reach a command line or a temporary file the caller must clean up:

```bash
echo "$UNTRUSTED_PROMPT" | cdx run work --cwd /path/to/repo --prompt-file - --json
```

It fails immediately if standard input is a terminal, rather than blocking at a silent prompt.

**Poll for completions with a cursor.** `cdx runs --since` returns every run that completed after the cursor, using the same cursor forms as `cdx history --since`:

```bash
cdx runs --since 15m --json
cdx runs --since 2026-08-07T09:00:00Z --json
```

A cursor is bounded by time, not by row count: `--limit` is ignored when `--since` is given (and says so in `warnings`). That is deliberate — capping a cursor query by row count would silently drop completions a caller had not yet seen, which is exactly the miss the cursor removes. Runs still in flight are not returned; they appear once they complete. Callers do not need to keep their own set of already-reported run ids.

**React to failures by code, not by message.** Argument failures report a specific `error.code` and name the offending arguments as data:

| `error.code` | Raised when |
| --- | --- |
| `missing_required_argument` | A required argument is absent |
| `mutually_exclusive_arguments` | Two arguments that cannot be combined were both given |
| `invalid_argument_value` | A constrained option got a value outside its accepted set |
| `argument_value_out_of_range` | A numeric argument fell outside its accepted range |
| `unknown_argument` | An unrecognized flag |

```json
{
  "ok": false,
  "error": {
    "code": "mutually_exclusive_arguments",
    "message": "cdx run: cannot specify both a session name and --provider.",
    "arguments": ["session", "--provider"],
    "allowed_values": null
  }
}
```

Never branch on `error.message`; it is written for a human reading a terminal and may be reworded.

**Discover valid values.** `cdx schema --json` publishes the enums and argument constraints the parser itself validates against:

```bash
cdx schema --json
```

It returns accepted values for `permission` (with its aliases and canonical forms), `reasoning_effort`/`power`, `kind`, and `provider`, plus the declared mutually-exclusive argument groups and the error codes above. Validate against this rather than copying the lists into your own code — a hand-maintained copy drifts, and cdx will not tell you when it does.

**Surface run warnings.** The run payload's `warnings` list reports degradations a zero exit code would otherwise hide, on the successful path as much as the failing one:

```json
{
  "ok": true,
  "exit_code": 0,
  "warnings": [
    {
      "code": "network_disabled_by_permission",
      "message": "codex runs at permission 'review' inside a sandbox with no network access, ...",
      "provider": "codex",
      "permission": "review"
    }
  ]
}
```

Codex ties network access to its sandbox, so any permission below `full` leaves the run unable to resolve DNS — `gh`, `curl`, and package installs fail inside an otherwise successful run. Show these warnings to whoever reads your output rather than discarding them; a run that succeeds while quietly doing less is the case they exist for.

Claude result records with nonempty `permission_denials` produce a warning with code `permission_denials`, the `provider`, and the structured `permission_denials` list. Exit code 0 still means `ok: true`: a denied tool may have been replaced successfully. Empty or absent denials add no warning. With `--scrub-env on`, Claude forces its default permission mode; allow tools needed by unattended runs explicitly using `--allowedTools` via `--extra-args` (see [operations](operations.md)).

### Local isolated Claude authentication

`cdx run <profile> --isolate-workspace` uses the setup token stored in
`<profile-home>/credentials/default.json`, including when the profile also has a
full claude.ai login. Only the setup token value enters the provider environment;
the profile home, full-login credential file and refresh tokens are never mounted
or passed into the sandbox. Interactive sessions and ordinary headless runs keep
preferring the full login so claude.ai connectors remain available there.

Without a stored setup token, the isolated run fails before starting the provider
with JSON error code `isolated_claude_token_missing`. Run `cdx login <profile>` to
store a setup token, or select a setup-token profile. An ambient OAuth token or a
full login alone cannot satisfy this requirement. Remote Claude continues to use
its separate dedicated token configured with `cdx auth claude-token <profile>`.

### Source repository attribution and external launchers

CDX captures `project` (an absolute canonical source repository path) and
`project_source` before starting a provider or applying workspace isolation.
Normal Git launches use the repository root, including launches from subfolders.
Linked Git worktrees use their common Git directory's source repository, so
normal and worktree launches share an identity even after worktree deletion.
Unrelated repositories with the same basename retain separate full-path keys.
Without Git evidence or an explicit source, attribution is unknown (`project:
null`, `project_source: "unknown"` in history; `project: "-"` in project stats).
Old cwd-only history also stays unknown: stats never inspect today's filesystem
or profile settings to guess yesterday's project.

Trusted producers such as an orchestrator must resolve the source repository
**before** creating a disposable mission directory, worktree, or temporary clone,
and pass it to the installed CDX launcher:

```bash
cdx run work --cwd /temporary/mission --project /repos/example-project --prompt 'Fix the issue' --isolate-workspace --json
cdx work --dir /temporary/mission --project /repos/example-project
```

`--project` is a trusted operator assertion, not provider output, a profile
setting, or an environment variable. It must be an absolute normalized path,
with symlinks already resolved by the producer; it may refer to a deleted source.
A plain temporary clone has no reliable link to a local source repository: the
producer must supply `--project` rather than expecting inference from a remote
URL or directory naming convention. Existing launch-directory validation and
execution `cwd` are unchanged. CDX records the separate identity in history,
runtime/registry records, and launch/result JSON. Failover attempts and detached
children retain the launch identity. `--continue-run` inherits the parent's
recorded identity (including unknown) and rejects a different `--project`.
Neither continuation nor backfill reattributes an older run from current profile
configuration.

Consumers should use stats `project` as the stable grouping key and
`session_name` as the disambiguated display label. In particular, dependent
example-project `scripts/cdx-stats.py` should not reduce `project` to `Path(...).name`:
that loses disambiguation between unrelated repositories named alike. Token,
duration, cost, and attempt counts keep the existing accounting rules; the
existing `totals.sessions` field counts groups for the chosen grouping.

### Recover historical project attribution

```bash
cdx history backfill-projects --mapping projects.json           # Preview (default)
cdx history backfill-projects --mapping projects.json --dry-run --json
cdx history backfill-projects --mapping projects.json --apply
```

The mapping format is deliberately generic, with exact CDX run IDs, not mission
IDs, profile names, prefixes, or cwd values:

```json
{"version":1,"projects":[{"run_id":"exact CDX run id","project":"/repos/example-project"}]}
```

Operators must build this file from attributable external evidence, such as an
exact launch receipt. CDX never imports the orchestrator, scans its private state, guesses
from disposable path prefixes, or resolves deleted worktrees. The supplied
Host A observation (84 disposable groups attributed by receipts to example-project
66, cdx-manager 10, logics-manager 6, city-jump 2) is diagnostic evidence, not a
mapping: actual exact CDX run IDs must be obtained on Host A before repair.

Without a mapping, the command can recover only from trusted project fields
already preserved for the exact run in CDX history or its run registry. A cwd-only
report is insufficient evidence. All attempts sharing an exact run ID must agree.
Invalid schema, contradictory duplicate mapping entries, and unknown exact run
IDs fail validation. An attribution conflict with known history or recorded run
evidence blocks the entire batch, preserving the original history and returning
exit status 1 with the conflict counts.

Results report `recovered` (recoverable history rows), `unchanged`, `unresolved`,
and `conflicting` counts, plus `applied` and `backup_path`. Counts are history
attempts, matching existing history accounting. Dry runs write nothing. Apply
holds the existing history lock, writes an original-byte `.projects-*.bak`
backup, and atomically replaces history only when the complete batch has no
conflict. Unrelated fields, usage, and malformed/unrelated history lines survive.
Repeating the same mapping is a no-op and creates no additional backup. The
registry and provider transcripts are never rewritten by backfill.

### Workstation update checks

`cdx update all --json` collects a read-only plan. `--yes` applies its supported
update and session setup steps. Existing `plan.items` fields remain available:
`installed`, `version`, `latest_version`, `update_command`, and `status`.
Versions and commands are explicitly `null` when unavailable.

- `up_to_date`: both versions are known and identical.
- `update_available`: the published version is newer (the tool is outdated).
- `unknown`: the source failed, returned invalid data, timed out, or the installed
  version could not be compared reliably. This never means up to date.
- `not_installed`: the executable is absent; no installation is guessed.

Checks use the npm registry for Codex and `@anthropic-ai/claude-code`, GitHub's
`rtk-ai/rtk` latest stable release, and Ollama's own `/api/update` endpoint with the local
OS/architecture and baseline version `0.0.0`. Ollama's local `/api/version` reports
an installed server, not the latest published release, and is not used.
Antigravity's editor `/releases` feed does not describe the `agy` CLI and is not
queried. `agy update --help` documents no read-only version check, so its latest
CLI version stays unknown (`latest_version: null`, `status: unknown`). CDX still
includes `agy update`, the CLI's own updater, in the plan. It runs only with
`--yes` or confirmation. Inventory collection never runs that updater.
HTTP and read-only CLI probes have a five-second timeout; source failures leave
`latest_version: null` and `status: unknown`. Ponytail also reports `unknown`
when its remote revision is unavailable. An empty, failed, or invalid Ollama
response (including Linux HTTP 204) falls back to the latest stable GitHub
release for `ollama/ollama`. If that source also fails, status is `unknown`;
a different platform's vendor response is never substituted.

For an outdated tool, CDX uses a native update command advertised by its
`--help` on either stdout or stderr (including Claude and RTK
when available), Codex's updater,
or Homebrew only when the resolved executable belongs to a Caskroom/Cellar
package. An outdated tool without such a path retains `update_available`,
`update_command: null`, and a human-readable `reason`; it requires the vendor's
manual update mechanism. On Linux, Ollama always retains `update_available`
with `update_command: null` and an explicit maintenance reason: its installer
writes system paths and may restart a service. A binary in `~/.local/bin` can
also serve running models, so CDX neither replaces it nor restarts services.
Arrange a manual maintenance window. Source uncertainty never schedules a guessed install.
The text table shows `UNKNOWN` and the reason, and an empty action list makes
no claim that all tools are current. JSON consumers, including external
example-project auto-update scripts, should inspect statuses separately from successful
command execution: exit code zero means no attempted action failed, not that
every installed tool was verified current. With `--yes`, the returned plan is the
pre-update inventory; `results` records attempted actions and their exit codes.

After each successful tool update command, CDX probes the CLI version again.
A raised version succeeds when it reaches the published release, if known.
An unchanged version also succeeds when the updater explicitly reports
`You are already on the latest version.` on stdout or stderr and exits zero;
this does not change an `unknown` inventory status to `up_to_date`.
Otherwise an unchanged, unreadable, downgraded, or still older-than-published
version makes the action fail, even if the updater exited zero. Successful text output
shows the before/after versions, including major upgrades. JSON keeps the
pre-update plan and existing result fields; tool verification adds
`version_before`, `version_after`, and `latest_version` to successful-command
results, plus `reason` and a nonzero `returncode` if verification fails.

## Find interactive conversations

`cdx history --interactive --cwd /path/to/project --limit 50 --json` finds interactive launches without mission runs consuming the result window. `--cwd` compares resolved paths (including symlinks and `~`), exactly, without including child directories. Both filters apply before `--limit` and also work with profile names, period filters and `--summary`. `--interactive` excludes headless `run` entries, detached entries and labels starting with `mission:`; unlabelled legacy launches remain eligible.

Interactive launches appear as `status: "running"` as soon as the provider starts, including `cdx start <name> --dir PATH` (an alias for `cdx <name> --dir PATH`) inside tmux. Completion or failure updates the same run ID. Active runtimes from older supervisors are included while their process remains alive; vanished unrecorded launches cannot be reconstructed.

History entries expose `conversation_id` and `provider_transcript_match: "conversation_id"` when an exact provider transcript exists. Claude uses its launch session ID; Codex can recover a unique thread from transcript metadata matching the launch directory and time window. Ambiguous discovery remains `provider_transcript_match: "recency"`, an explicitly unverified fallback that must not be treated as a verified resume target. A known ID with no transcript does not borrow another conversation. Existing history is enriched on read without rewriting old rows.

`first_user_prompt` contains the first real user text (up to 2,000 characters) from a bounded, redacted transcript read. Provider command wrappers, system reminders, tool results and bare absolute file paths are skipped. Missing, oversized or unavailable evidence leaves the prompt unknown; a supplied initial prompt is used when available.

### Resolve the conversation of a live Codex process

Consumers such as example-project can request process-scoped resolution without
falling back to workspace/recency:

```bash
cdx conversation work2 --pid 12345 --tail 20 --json
cdx conversation work2 --process-identity 'linux:12345:<opaque digest from response>' --json
```

Supply the native Codex PID, not the shell, tmux pane PID, Node launcher, or CDX
supervisor. CDX does not traverse descendants or choose between processes.
`work2` supplies the provider/profile boundary; its saved conversation is ignored
in process mode. The selectors are mutually exclusive and cannot be combined with
`--conversation`, `--cwd`, or `--since`.

The Python API is `read_conversation("codex", auth_home, pid=12345, tail=20)` in
`cdx_manager.conversation` (`src.conversation` in a source checkout). Retain
`process_identity` and pass it instead of `pid` on later calls to reject PID reuse.
A bare PID identifies its current occupant, not a previously observed process.
The opaque identity is a lifetime guard, not an authorization grant.

Process-selected pages expose:

| Field | Current contract |
| --- | --- |
| `resolution_status` | `resolved` for verified native rollout evidence, otherwise `unknown` |
| `resolution_method` | `process_open_rollout` when resolved, `app_server_open_rollout` for a remote-controlled Codex TUI, otherwise `null` |
| `conversation_id` | Native `session_meta.payload.id`, checked against the open rollout filename |
| `process_identity` | Opaque Linux lifetime guard when process validation succeeds |
| `reason` | `null` on success; explicit evidence boundary or process validation failure otherwise |

On Linux, CDX inspects only the supplied PID's open descriptors. A unique writable
`rollout-…-UUID.jsonl` under the selected profile's `sessions/` directory supplies
the native identity. Its first record must be a complete `session_meta` with a
matching UUID and `source: "cli"`. Duplicate descriptors for the same file count
once; read-only descriptors do not establish the active writer. Multiple distinct
writable rollouts return `ambiguous_native_rollouts`, even if one is newer. A
rollout outside the selected profile returns `profile_boundary_mismatch` before
its contents are read. Resolved symlinks must remain inside the profile, including
the `sessions/` root. No workspace, mtime, saved resume ID or recency fallback is
used, even if `fallback_to_recency=True` is supplied through Python.

With remote control on, the Codex TUI (`codex --remote`) writes no rollout: the
`codex app-server` cdx started beside it does, with `source: "vscode"`. For that
case only, pass the TUI PID: CDX reads the session's own remote-control endpoint
file, which its launcher writes with the TUI and app-server PIDs, checks that both
are still children of that launcher and that the app-server is a `codex` process
of the same user, then applies the same descriptor, profile and header checks to
the app-server, accepting `source` `cli` or `vscode`. The returned
`process_identity` still guards the TUI PID. Without that endpoint file, a
non-remote PID is resolved exactly as before and an app-server PID passed
directly stays refused.

This is a snapshot of the process's sole native rollout writer. A rollout must
already exist and remain open for writing; a fresh thread before its first
rollout returns `native_conversation_identity_unavailable`. A retained writer
and another open writer are ambiguous. The resolver does not infer TUI focus
from file timestamps or claim to observe selection changes without a writer
change. Consumers must treat unknown as unknown and must not retry via recency.

The exact open file's device/inode is checked against its profile path before
reading. CDX rechecks the lifetime guard and native rollout evidence before and
after the message read. A detected exit, PID reuse, switch, replacement or lost
proof discards all entries. These checks are snapshots, not an atomic provider
selection subscription; the process can change after the final check.

Resolved requests return `status: "ok"` and normalized entries, including support
for `--tail`. Unknown requests return `status: "unavailable"`, no entries and a
null conversation ID. Process pagination remains disabled: no cursors are issued,
`has_more` is false, and `--cursor` or `--before` returns `reset_required` without
entries. Poll again using the retained process identity and `--tail`; an
explicit-ID or recency cursor cannot cross into process mode. Existing explicit-ID
and recency pagination contracts are unchanged.

Only Linux `/proc` and interactive Codex are supported. Each evidence pass reads
at most 8 KiB each from `stat`, `status`, kernel `boot_id` and each candidate's
`fdinfo`, enumerates at most 512 descriptors, and reads at most 64 KiB of each
candidate's metadata header. Message reads use the existing bounded conversation
reader and redaction. The lifetime guard includes PID, start ticks, boot ID, all
four target UIDs and executable device/inode. Wrong user, a non-`codex` executable,
dead/reused PID, inaccessible/oversized/malformed evidence, or unsupported
provider/platform fails closed. Reasons include `unrelated_user`,
`unrelated_process`, `process_not_running`, `process_identity_changed`,
`native_evidence_unavailable`, `invalid_native_rollout`, `evidence_changed`,
`evidence_limit`, and `unsupported_process_resolution`. No argv, environment,
credential store, descendant traversal, profile transcript search or history
database participates in process resolution. No launch flags or dependencies
change. Host A's authenticated TUI still requires a measured comparison of the
returned UUID with its selected native conversation after launch, resume and
switch, especially with concurrent sessions.
