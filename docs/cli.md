# Command reference

## All Commands

| Command | Description |
|---|---|
| `cdx` | List all sessions with last-updated timestamps |
| `cdx --json` | List all sessions as a machine-readable JSON payload |
| `cdx <name>` | Launch a session (checks auth first) |
| `cdx <name> [--json]` | Launch a session; `--json` returns a structured success payload after the interactive run ends |
| `cdx <name> -r` / `cdx <name> --resume` | Resume the provider-native conversation for a session when supported |
| `cdx add [provider] <name> [--model MODEL] [--json]` | Register a new session (`provider`: `codex`, `claude`, `antigravity`, or `ollama`; Ollama requires `--model`) |
| `cdx cp <source> <dest> [--json]` | Copy a session into another session name, overwriting the destination if it exists |
| `cdx ren <source> <dest> [--json]` | Rename a session and move its auth data |
| `cdx label <name> <label> [--json]` | Attach one short label to a session; tables show `LABEL` only when at least one label exists |
| `cdx label <name> --clear [--json]` | Clear a session label |
| `cdx login <name> [--json]` | Re-authenticate a session (logout + login) |
| `cdx logout <name> [--json]` | Log out of a session |
| `cdx auth refresh <name\|all> [--json]` | Make a locked, non-generation Codex auth probe; reports `login_required` when interactive login is needed |
| `cdx disable <name> [--json]` | Disable a session without deleting it; disabled sessions stay visible and cannot launch |
| `cdx enable <name> [--json]` | Re-enable a disabled session |
| `cdx config <name> [--json]` | Show persistent launch settings for a session |
| `cdx configs [--json]` | Show persistent launch settings for all sessions in one table |
| `cdx power\|perm\|fast\|model <name\|all\|provider:PROVIDER\|a,b> <value\|default> [--json]` | Shortcut commands for setting or clearing one launch setting |
| `cdx set <name>\|--sessions all\|a,b\|--provider PROVIDER [--power minimal\|low\|medium\|high\|xhigh] [--permission review\|default\|auto\|full] [--fast on\|off] [--rtk on\|off] [--logics on\|off] [--model MODEL] [--fallback-model MODEL[,MODEL...]] [--budget USD] [--extra-args 'ARGS'] [--priority 0..100] [--json]` | Persist launch settings for one or more sessions |
| `cdx unset <name>\|--sessions all\|a,b\|--provider PROVIDER (--power\|--permission\|--fast\|--rtk\|--logics\|--model\|--fallback-model\|--budget\|--extra-args\|--priority\|--all) [--json]` | Remove persisted launch settings and fall back to provider defaults |
| `cdx history [name] [--limit N] [--summary] [--since 7d\|today\|DATE] [--from DATE] [--to DATE] [--json]` | Show recent launch history or aggregate total launch time per assistant, optionally filtered by period |
| `cdx last [--json]` | Launch the most recent existing session from launch history |
| `cdx resume <name> [--json]` | Resume the provider-native conversation for a session using the named command form |
| `cdx can-resume <name> [--json]` | Check whether a session supports native resume without launching the provider |
| `cdx context show\|path\|init\|edit\|clear\|set\|append [text...] [--json]` | Manage the shared Markdown context for the current workspace |
| `cdx memory [--global\|--project NAME_OR_PATH] [show\|view\|path\|init\|edit\|clear\|set\|append\|list] [text...] [--json]` | Manage explicit user-controlled memory for the current workspace, global scope, or a named/path project |
| `cdx handoff <name> [--json]` | Reuse the prepared entry for this target/workspace, or use explicitly labelled notes-only recovery if none exists; launch unless `--json` |
| `cdx handoff <source> <target> [--source-conversation ID\|--source-native-transcript PATH\|--source-transcript PATH] [--json]` | Prepare an identity-checked transcript entry and launch the target in the verified workspace unless `--json`; exact native selection resolves duplicate IDs, while explicit terminal selection is degraded recovery |
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
| `cdx update all [--yes] [--json]` | Check installed providers, RTK, and Ponytail across Codex profiles; show the plan and ask once before applying safe native/Homebrew updates and missing RTK/Ponytail setup |
| `cdx ready [--refresh] [--json]` | Schedule an OS notification for the next cooling-down assistant that becomes ready, then return immediately |
| `cdx notify` | Internal provider hook target for agent alerts; use `cdx set <name> --notify on` to enable it |
| `cdx next [--json] [--refresh]` | Select the best next assistant using the same priority logic as `cdx status` |
| `cdx select --provider PROVIDER [--min-reasoning-effort minimal\|low\|medium\|high\|xhigh] [--min-power minimal\|low\|medium\|high\|xhigh] [--require-ready] [--refresh] --json` | Select a suitable session for headless automation |
| `cdx run [session] --cwd PATH (--prompt-file PATH\|--prompt TEXT\|--prompt-file -) [--provider PROVIDER] [--model MODEL] [--reasoning-effort minimal\|low\|medium\|high\|xhigh] [--power minimal\|low\|medium\|high\|xhigh] [--permission MODE] [--timeout-seconds N] [--detach] [--failover] [--refresh] --json` | Run one headless task and return a stable JSON result; `--detach` returns the `run_id` at launch without waiting, `--failover` continues the task on the next account when this one hits its rate limit, `--prompt-file -` reads the prompt from stdin |
| `cdx run-report <run_id> --json` | Full report, transcript metadata, and final payload for a run |
| `cdx run-status <run_id> --json` | Status of one run by id |
| `cdx run-tail <run_id> [--lines N] --json` | Last lines of a run's own output, while it is still running or after it finished |
| `cdx runs [--limit N] [--since 7d\|today\|DATE] --json` | List recent runs; `--since` returns every run completed after the cursor and ignores `--limit` |
| `cdx schema --json` | Publish the enums, mutually-exclusive argument groups, and error codes programmatic callers should validate against |
| `cdx stats [name] [--since 7d\|today\|DATE] [--from DATE] [--to DATE] [--json]` | Aggregate launch counts, duration, and known token usage by session, for headless and interactive runs alike |
| `cdx status [--json] [--refresh\|--cached] [--timeout SECONDS]` | Show token usage table for all sessions; empty credits, block, and reset columns are omitted; `--cached` skips live provider probes and returns only stored status |
| `cdx status --small [--refresh\|--cached] [--timeout SECONDS]` / `cdx status -s [--refresh\|--cached] [--timeout SECONDS]` | Show compact token usage table without provider, blocking quota, credits, and updated columns |
| `cdx status <name> [--json] [--refresh\|--cached] [--timeout SECONDS]` | Show detailed usage breakdown for one session; `--cached` avoids live provider refreshes |
| `cdx tray status [--json] [--refresh]` | Emit the tray snapshot: one icon state, one line per enabled session, and how fresh each figure is. Reads stored status by default; `--refresh` is the only path that probes a provider |
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

Known headless and completed interactive token usage is persisted in launch history and can be aggregated later. Interactive records are best-effort local data: Codex reads its latest cumulative rollout snapshot, Claude reads its assistant usage records, and Ollama — which writes no transcript of its own — is launched with `--verbose` so its per-response token counts land in the terminal capture cdx already takes. Antigravity reports no usage: its history is schema-less binary protobuf and its logs carry no usage line, so those sessions show no tokens by nature rather than by omission.

Every usage record, whichever path produced it, uses one set of definitions:

| Field | Meaning |
| --- | --- |
| `input_tokens` | Uncached input **only**. Codex reports a cache-inclusive count natively; cdx reduces it to the remainder so the field means the same thing on every provider. |
| `cache_creation_tokens` | Tokens written to the provider's prompt cache. |
| `cache_read_tokens` | Tokens served from it. Kept apart from cache creation because the two cost roughly 1.25x and 0.1x of uncached input, a difference no summed figure can recover. |
| `cached_input_tokens` | `cache_creation_tokens + cache_read_tokens`, derived. The single CACHE column in `cdx stats` shows this. |
| `output_tokens` | Generated tokens. |
| `reasoning_tokens` | Reasoning the provider counts separately. Codex reports one; Claude does not, because it bills thinking as output — those tokens are already inside `output_tokens`, so an empty REASON column for Claude is correct rather than missing. |
| `total_tokens` | `input + cache_creation + cache_read + output`. Cache is typically the bulk of real consumption, so a total that left it out would not be slightly low — it would be a different quantity. |

Cached input is counted once: it is excluded from `input_tokens` and reported in the cache fields, never in both. `null` means the provider did not report the figure, which is not the same as zero.

`cdx stats` also shows a **`COST~`** column and ranks sessions by it. It weights each token class by what it costs relative to one uncached input token — cache read at the recorded model's ratio (0.1x by default), cache write 1.25x, and output at the recorded model's output/input ratio — and reports the result in uncached-input-equivalent tokens. These are ratios rather than prices. It is **not** a currency amount, and it is not comparable across providers whose own prices differ. The cache-write multiplier assumes the five-minute cache TTL; a one-hour TTL costs 2x and nothing in a transcript says which was used, so long-TTL writes are slightly under-weighted.

Ranking on the raw total would put a session that mostly replayed a cache above one that spent far more on generation, because cache reads are typically the overwhelming majority of tokens consumed while costing a fiftieth of an output token.

The **`USD~`** column turns that into money for runs whose serving model cdx recorded. It prices each token class directly using the built-in model table. To customize prices: set `CDX_TOKEN_PRICES` to a JSON object mapping model id to dollars per million tokens to override the built-in table, whose last review date is printed with the totals. A run whose model cdx never saw stays unpriced rather than being charged at a default tier, and the totals line says how many runs were actually priced.

The table requires `input` and `output` prices in USD per million tokens and accepts an optional `cache_read` price in the same units. Without it, cache reads cost 0.1x input; cache writes assume 1.25x input. GPT-6.1 Sol and Claude Opus 5.5 use 0.05x cache reads, while Claude Fable/Mythos 5.1 use 0.025x. Both `COST~` and `USD~` honor those rates. `CDX_TOKEN_PRICES` replaces the supplied model row: a two-field override keeps the legacy 0.1x fallback; include `cache_read` to override it (including zero).

Override rates must be finite and nonnegative. A zero input rate can still yield `USD~`, but ratios relative to input are undefined; `COST~` then shows `-` for an uncovered session. JSON keeps the numeric `weighted_tokens` sum for covered runs and reports `weighted_runs` and `unweighted_runs` so partial coverage is visible.

The figure uses standard public list prices, excluding Fast/priority, Batch/Flex, regional premiums, and tool fees — not an invoice. When a run changes models without a measured per-model token split, its USD estimate is unavailable rather than assigning all tokens to one model. OpenAI's long-context tier, which increases rates above a 272K-token request, is **not** modelled: cdx records tokens per run rather than per request, so it cannot tell which requests crossed that line, and long-context Codex work is under-costed.

`cdx stats` counts completed history attempts. A headless failover has one logical run in `cdx runs` but one history row per attempted session, including failed attempts that reported usage. Period filtering includes the entire run in every period it overlaps, so adjacent daily results can both include a run crossing midnight; adding daily totals may exceed a combined period. JSON `accounting` names this policy and the current price-table source. `usage_runs` and `priced_runs` show how much of the token total has a dollar estimate. Live runs are absent until their history row is written, and unknown usage is different from measured zero.

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
