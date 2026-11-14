# Features

## Quota-aware routing

The reason `cdx` exists: knowing, across every account you own, which one you can actually use.

- **Usage at a glance.** `cdx status` shows token usage, 5-hour window quota, weekly quota, last-updated timestamps, priority guidance, and the last launched session in one aligned table.
- **Pick for me.** `cdx next` selects the best available assistant from your pinned priorities and the live quota picture, shows the reason, and prints the exact command to run.
- **Agent notifications.** At the first interactive launch of a supported provider, cdx asks before installing its hook. Delivery starts muted; `cdx tray alerts on` enables the next event globally, with or without the tray running.
- **Next-ready notification.** `cdx ready` schedules a native system notification for the next assistant that comes back from cooldown, then returns immediately.
- **Passive status resolution.** Codex status is read from the local Codex app-server rate-limit API when available, with legacy transcript/history parsing kept as a fallback.
- **Banked reset visibility.** Eligible Codex accounts show the number of manually redeemable bonus resets in `cdx status` and expose reset details in JSON output.

## Isolated multi-account sessions

![cdx: every registered session with its provider, state, pinned launch settings and age](assets/list.png)

- **Multiple providers, one tool.** Register as many Codex, Claude, Antigravity, or Ollama sessions as you need. Codex and Claude get isolated auth environments; Antigravity is launchable through `agy` with OS-keyring auth; Ollama runs local models through `ollama run`.
- **Instant launch.** `cdx work` opens your "work" session. `cdx personal` opens another. No config files to edit mid-flow.
- **Quick relaunch.** `cdx last` reopens the most recently launched assistant profile.
- **Resume by identity, not by recency.** Each session records the provider's own conversation id — imposed at launch for Claude, read back from the rollout for Codex — so `cdx resume <name>` reopens *that* conversation regardless of your working directory or of which session ran last. The conversation is looked up before it is named: a recorded id whose transcript the provider never wrote degrades to the provider's own fallback (`--continue`, or `resume --last`) and reports `reason: conversation_not_found`, rather than naming a conversation that does not exist and letting the provider exit with an error. `cdx can-resume --json` reports the strategy and where the id came from, so an automated caller can tell a named resume from a best-effort one.
- **Auth guardrails.** `cdx` checks authentication before launching. If a session is not logged in, it tells you exactly what to run — no silent failures.
- **Persistent launch settings.** Pin per-session power, permission, and fast-mode preferences once; `cdx` reapplies them on every launch until you unset them.
- **Spend ceiling and model fallback.** `cdx set <name> --budget 5` caps what a headless run may spend, and `--fallback-model sonnet,haiku` lets a run continue on the next model when the first is overloaded. Both are Claude Code flags that the provider accepts with `--print` only, so they apply to `cdx run` and not to interactive launches; `cdx configs` says so.
- **Session control.** Disable a session without deleting it when an account is temporarily out of credits; disabled sessions remain visible and sort last.
- **Optional session labels.** `cdx label <name> <label>` adds a short human label; list and full status tables show a `LABEL` column only when at least one session has one.
- **Clean removal.** `cdx rmv` wipes a session and its entire auth directory. No orphaned files, no stale credentials.

## Headless automation

- **One task, one JSON result.** `cdx run` executes a prompt against a chosen or auto-selected session and returns a stable payload; `--detach` returns a `run_id` immediately.
- **Survives a rate limit.** `cdx run --failover` notices that a run stopped because its account ran out, moves the task to the next account the ranking allows, and carries on — one `run_id` for the whole task, with every account it occupied listed in `cdx run-report`. A spent account is always confirmed against its own refreshed quota first, so a healthy account is never abandoned. From there two routes migrate a run: the provider said so in words cdx recognises, or — since that wording differs between an enterprise workspace out of credits, a personal plan hitting its 5-hour window, and Claude's own phrasing — simply that the account's quota is gone and the run failed. `cdx run-report` names which route applied. Exhausting every account reports `failover_exhausted`, which a caller can tell apart from the task itself failing. It combines with `--detach`: the detached cdx process supervises the run, applies the same rule, and records each move in the run registry; such a run always uses cdx's own detached child rather than the provider's background agent, which nothing would be watching.
- **Native background delegation (opt-in).** With `CDX_EXPERIMENTAL_NATIVE_BG=1`, `cdx run --detach` hands the run to Claude Code's own background agents (`--bg`) instead of cdx's detached launcher. The run keeps its cdx `run_id`, closes out with its token usage and final answer read from the provider's own session transcript, and the parked session is stopped once its task is done. Off by default for one release while it settles; the in-house launcher is unchanged and is what every run takes otherwise. Codex keeps the in-house path while its `cloud`/`exec-server` surfaces are marked experimental.
- **Observable runs.** `cdx run-status`, `cdx run-tail`, `cdx run-report`, and `cdx runs --since` follow a run while it happens and after it ends.
- **Selection without launching.** `cdx select --provider ... --require-ready --json` answers "which session should this job use?" for orchestrators.
- **Escape hatch for unmapped flags.** `cdx set <name> --extra-args "--add-dir ../shared"` passes provider arguments cdx does not model straight through, so a flag your provider shipped last week never forces you to abandon cdx. These arguments are explicitly unvalidated: cdx does not parse or verify them, `cdx schema --json` lists them under `unvalidated` rather than describing them, and `cdx doctor --check-provider-flags` ignores them. They are split into literal argv entries and never passed through a shell.
- **Validated contract.** `cdx schema --json` publishes the enums, mutually-exclusive argument groups, and error codes programmatic callers should validate against.

## Context handoff

- **Transcript-first handoff.** Switch accounts or providers using the source conversation's recorded native identity and verified workspace. CDX never chooses a conversation by file modification time. Missing, stale or mismatched identity requires an explicit choice; JSON/non-interactive callers receive candidate diagnostics instead of a launch.
- **Instructions before action.** The receiving agent is told to read applicable `AGENTS.md`/`CLAUDE.md` and their required references (including Logics instructions), recover the task from bounded portions of the complete transcript, verify current state, then show a concise objective/state/next-action checkpoint before modifying anything. Existing clear authorization still permits continuation. CDX supplies this prompt; it cannot certify that an agent has understood or obeyed it.
- **Shared notes remain yours.** `cdx context` and `cdx memory` remain explicit notes. Automatic handoff does not overwrite them or copy authentication. A dated reference to workspace notes is supplementary, never a substitute for the native conversation.
- **Session transcript capture.** Every launch is recorded to a local log file via `script`, giving you a full terminal transcript for each session.

Run handoff from the intended project directory:

```sh
cd /path/to/project
cdx handoff source target --json                 # prepare only, no provider launch
cdx handoff target                               # use that prepared entry and launch
cdx handoff source target --source-conversation CONVERSATION_ID
# Exact native file when several transcripts share an identity:
cdx handoff source target --source-native-transcript /path/to/source/sessions/rollout.jsonl
# Explicit fallback when only a terminal capture is available:
cdx handoff source target --source-transcript /path/to/source/log/cdx-session.log
```

The three source-selection options are mutually exclusive and apply only to
`SOURCE TARGET`. Without a usable recorded identity, an interactive terminal offers
up to 20 valid conversations from the current workspace, ordered by actual event
time for inspection, with no default choice. Blank input or Ctrl-C cancels. A stale
recorded identity never silently falls back, even if there is only one candidate.
Run from the conversation's original workspace if its metadata names another directory.

Each preparation writes a private, unique `<target-auth-home>/handoffs/<uuid>.json`
entry. `context.target_path` in JSON output names that entry; `handoff` contains its
metadata, including recovery mode, source conversation ID, transcript path, workspace,
preparation time, readable byte extent and SHA-256. `source_session`/`target_session`
contain names/providers only. Transcript bodies and credentials are not emitted.
Unresolved JSON source selection returns `ok: false`, error code
`handoff_source_unresolved`, a bounded `candidates` array and a nonzero exit status.

The original JSONL remains in place, including early decisions, tool calls/results
and compaction records. Read it in bounded portions up to `extent_bytes`; there is
no 120000-character tail replacement. An unfinished final JSONL record is excluded
from that preparation. Later appends do not change its boundary. Reusing an entry
checks the original bytes: deletion, truncation or rewriting requires a new handoff,
not a silent downgrade to notes. Keep the original source profile/transcript available
until recovery completes. No transcript copy or automatic artifact cleanup is performed;
entries can be removed after use. A small per-workspace/target pointer chooses the most
recent preparation for the one-name command; concurrent launches retain their own entry
path and cannot overwrite each other's entry.

Legacy one-name handoff without a prepared entry reads workspace notes in `notes-only`
mode and explicitly reports that native history was not recovered. Terminal fallback
requires a named file from that source session's launch logs and is labelled `degraded`:
it cannot prove complete history or tools, and its workspace is operator-selected rather
than verified from native metadata. Native resolution currently supports Codex and Claude.
All modes ask the recipient to report material gaps, and none bypass provider access rules
or turn historical tool output into new authorization.

## Maintenance

- **Launch history.** Inspect recent launches with provider, result, duration, working directory, launch settings, and transcript path.
- **Aggregate usage.** `cdx stats` totals runs, token usage, and time spent per session over any period. Interactive Codex and Claude launches also record provider-native token totals when their local session transcript is available.

- **Disk usage and cleanup.** `cdx disk` reports `CDX_HOME` usage, `cdx disk profiles --candidates` identifies reclaimable profile caches/logs with evidence, and `cdx clean profiles ...` applies explicit cleanup actions.
- **Health and repair.** `cdx doctor` inspects dependencies, permissions, and orphan profiles; `cdx repair` plans or applies safe fixes.
- **Portable bundles.** `cdx export` / `cdx import` move sessions between machines, with passphrase-encrypted auth data when you ask for it.
- **Update prompts.** Periodic update checks surface `cdx update` directly in the `cdx`, `cdx status`, and launch output when a newer release is available. When `logics-manager` is installed, `cdx` can also suggest `logics-manager update`.
- **Logics viewer shortcut.** `cdx view` opens the Logics browser/focus viewer through `logics-manager view` when the companion CLI is installed. All viewer flags are forwarded: `--lan`, `--lan-rw`, `--focus <ref>`, `--read`, `--port`, `--host`, `--refresh-interval`, `--tls`, `--tls-cert`, `--tls-key`, `--open`, `--no-open`. `cdx view --json` reports availability and update diagnostics without opening the viewer.

## Automatic mission concurrency per profile

```bash
cdx set work --max-parallel 2
cdx show work
cdx unset work --max-parallel
```

`--max-parallel` accepts an integer from 0 to 5 and stores `launch.max_parallel`
next to `priority` and `policy`. Zero excludes the profile from automatic
missions. An absent value adds no profile-specific ceiling: the scheduling
client applies its own rule. Existing configurations need no migration.
`cdx unset work --all` also removes the limit.

The scheduling client is responsible for enforcing this metadata. It is
separate from the existing per-command `cdx run --max-parallel` limit.
`cdx --json` (also `cdx ls --json`) includes the optional field in each
session's `launch` object; `cdx status --json` exposes `max_parallel` on each
row (`null` when absent). `cdx show` is an alias for `cdx config` and displays
`Max parallel` as `default` when unset.

## Cache efficiency and fix rounds


`cdx history --interactive --cwd /path/to/project --limit 50 --json` finds interactive launches without mission runs consuming the result window. `--cwd` compares resolved paths (including symlinks and `~`), exactly, without including child directories. Both filters apply before `--limit` and also work with profile names, period filters and `--summary`. `--interactive` excludes headless `run` entries, detached entries and labels starting with `mission:`; unlabelled legacy launches remain eligible.

Interactive launches appear as `status: "running"` as soon as the provider starts, including `cdx start <name> --dir PATH` (an alias for `cdx <name> --dir PATH`) inside tmux. Completion or failure updates the same run ID. Active runtimes from older supervisors are included while their process remains alive; vanished unrecorded launches cannot be reconstructed.

History entries expose `conversation_id` and `provider_transcript_match: "conversation_id"` when an exact provider transcript exists. Claude uses its launch session ID; Codex can recover a unique thread from transcript metadata matching the launch directory and time window. Ambiguous discovery remains `provider_transcript_match: "recency"`, an explicitly unverified fallback that must not be treated as a verified resume target. A known ID with no transcript does not borrow another conversation. Existing history is enriched on read without rewriting old rows.

`first_user_prompt` contains the first real user text (up to 2,000 characters) from a bounded, redacted transcript read. Provider command wrappers, system reminders, tool results and bare absolute file paths are skipped. Missing, oversized or unavailable evidence leaves the prompt unknown; a supplied initial prompt is used when available.

`cdx history --json` records uncached input, cache reads, cache writes, output tokens, and `usage.cache_hit_ratio` beside the existing token totals. The ratio is cache reads divided by all input tokens, excluding output. Missing provider splits stay `null`, and text views show `cache n/d` instead of claiming a zero hit rate.

`cdx stats --json` adds `cache_usage` sums and an input-weighted `cache_hit_ratio` to each session, project (`--by project`), model (`--by model`), and total. `cache_usage` preserves unknown sums as `null`; existing numeric aggregate fields keep their previous behavior. Ratios include only runs with measured input and cache reads. Coverage is explicit in `measured_runs` and `measured_input_tokens`. `run_types.cold` and `run_types.continued` expose counts, sums, and ratios for comparison. Text views show values such as `cache 72 %` next to tokens.

Reuse a completed run's provider conversation for another fix round:

```bash
cdx run work --cwd /path/to/repo --prompt "Implement the change" --reasoning-effort high --json
cdx run --continue-run RUN_ID --cwd /path/to/repo --prompt "Fix the remaining test failure" --json
```

Pass provider arguments for a single run with `--extra-args 'ARGS'`. They use the session setting's POSIX quoting and validation (nonempty, at most 512 characters, no control characters, balanced quotes), and are appended after the profile's `extra_args`. They do not change the profile or subsequent interactive launches. Provider flag semantics remain unvalidated, as listed under `unvalidated.extra_args` in `cdx schema --json`; existing provider permission and workspace isolation handling still applies. Codex headless launches retain their existing behavior of ignoring session and run extra arguments.

```bash
cdx run claude-work --cwd /path/to/repo --permission default --prompt 'Run: touch t' --extra-args '--allowedTools "Bash(touch t)" --strict-mcp-config' --json
```

This allows the requested Claude tool and restricts MCP configuration for this run only. The option also follows detached runs and profile failover. With `--continue-run`, Claude extra arguments that override model, effort or conversation are refused, whether supplied by the session or this run.

`--continue-run` resumes the exact Claude session or Codex thread and pins the previous run's recorded model and effort, even if the profile settings changed. The profile is inferred from the parent; an explicit session or provider must match. An explicit model or effort must also match. Runs and history record `parent_run_id` and `conversation_id`. Detached continuations use the cdx child supervisor with the same pins. Codex continuation usage is measured between exact transcript snapshots before and after the run, since exec resume can report conversation totals. If either boundary is unavailable, per-run usage stays unknown with `usage_attribution: "continuation_usage_unavailable"` in history instead of counting earlier turns again.

Headless runs, including detached, remote and continued runs, keep their
conversation identity in run records and history without replacing the profile's
interactive conversation.

Conservative assumption: a continuation requires a finished Claude or Codex run, a locally available provider transcript, and recorded model and effort settings. Missing runs, profiles, expired sessions, and unavailable settings produce a clear error; the caller can retry without `--continue-run` for a cold run. `--failover` and `--isolate-workspace` cannot be combined with continuation. Capacity recovery and provider model fallback are disabled for continuations so they cannot silently switch model or account. Provider cache retention remains provider-controlled, so resuming does not guarantee a cache hit.

## Run costs and budgets

`cdx history --json` includes nullable `cost_usd` for each entry, estimated from its observed usage and serving model using the same table and `CDX_TOKEN_PRICES` overrides as `cdx stats`. Unknown prices or usage stay `null`.

```bash
cdx run work --cwd /path/to/repo --prompt "Fix the tests" --budget 2.50 --json
```

`--budget` stops a run once its measured estimated cost reaches the USD amount, including with `--detach` and `--continue-run`. A budget stop exits with code 125 and reports `error.code: "budget_exceeded"` and `error.spent_usd`. Detached callers read the final result through `cdx run-status` or `cdx run-report`. Usage arrives in provider updates, so the estimate can overshoot; unknown usage or prices cannot trigger a budget stop. See the [budget contract](cli.md#run-budgets) for details.

## Codex model capacity recovery

`cdx run` (including `--detach`) automatically recovers from Codex's "Selected model is at capacity" failure. It retries the same prompt, profile, and model after 1 and 2 seconds, then tries the profile's `fallback_model` list in configured order, removing duplicates. Configure alternatives with `cdx set work --fallback-model MODEL_A,MODEL_B`.

After exhausting those models, CDX selects another ready Codex profile using the normal ranking, including profile priority. Disabled, logged-out, `never`, and `ask-first` profiles are excluded from automatic selection. To choose an `ask-first` profile explicitly, name it in a new command (`cdx run NAME ...`). Each successor uses `--model` if supplied, otherwise its own configured/default model, followed by its own fallback list. Each model gets at most three attempts; at most four profile switches are allowed. Settings are not changed. Each attempt retains the command's timeout; the backoff adds at most three seconds per model.

Recovery does not require `--failover`, which still controls account quota exhaustion separately. Other provider failures and timeouts do not trigger capacity recovery. Attempts restart the prompt in the same workspace; files from earlier attempts remain there. Each retry, model fallback, profile fallback, and exhausted budget is logged to stderr and persisted in `recovery_events` in the run registry and final JSON (`cdx run-status` / `cdx run-report`). Events include archived attempt output paths. Recovery keeps one run ID and reports the final effective model. If no eligible alternative remains or the profile switch budget is reached, the run fails with `capacity_recovery_exhausted`.
