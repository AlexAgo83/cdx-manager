# Unreleased

## Read-only isolated inputs (next patch)

- Add repeatable `cdx run --isolate-workspace --ro-input NAME=PATH` to mount owner-controlled directories read-only under `/opt/inputs/` and expose their sandbox paths through named environment variables. Refuse invalid or reserved names, duplicate names, missing directories, top-level symlinks, foreign ownership and paths overlapping the workspace, configuration, state or credentials.
- Persist inputs through detached runs and continuations, revalidate before launch, and advertise `capabilities.ro_inputs = 1`. Cover local and shipped-worker mounts, validation, continuation and schema behaviour.

## Claude continuation settings snapshots (next patch, #131)

- Copy validated permissions-only settings into a private run-state file with mode 0600 using atomic writes, and pass its path to Claude. Large settings files no longer exceed the launch argument limit; user-supplied argument validation remains unchanged. Retain the continue-time content with the run state and mount snapshots read-only for isolated continuations.
- Cover settings larger than 512 characters, recorded private paths, owner-only permissions, cleanup, isolated mounts and source changes before launch for profile and per-run settings.

## Claude continuation permissions (next patch, #129)

- Accept permissions-only `--settings` in profile and per-run extra arguments during `--continue-run`, using either separate or equals syntax and inline JSON or a UTF-8 file. Snapshot the validated object to prevent file changes from altering the launch.
- Reject every other settings key with its name and `continue_run_settings_mismatch`; reject unreadable files, invalid JSON and non-object values. Preserve all other pinned-option refusals.

## Per-run provider arguments (#120)

- Add `cdx run --extra-args 'ARGS'` with the session setting's validation and POSIX splitting, appended after the selected profile's arguments without changing saved settings or interactive launches. Preserve existing provider permission and isolation handling.
- Forward run arguments to detached supervisors and profile failover; reject Claude model, effort and conversation overrides during continuation. List the option under `cdx schema --json` unvalidated arguments and cover run-only Claude tool allowlists and strict MCP configuration.

## Claude profile quota status line

- Install a fast cache-only status line for Claude profiles at creation, settings updates and interactive launch/resume. Show the shared launcher gauge, both remaining windows, profile name, low-quota resets and a stale marker; use `quota ?` when data is unavailable.
- Preserve and report operator-defined status lines. Add `cdx set --status-line on|off` and `cdx unset --status-line` for reversible profile control; leave Codex settings unchanged and document its built-in footer equivalent.
- Write the standalone status line as UTF-8 when piped, including on Windows, and read repository contract fixtures explicitly as UTF-8.


## Quota provenance and profile freshness

- Add `quota_windows.5h` and `quota_windows.weekly` to status JSON with `source`, per-profile/window ISO `observed_at`, `availability` (`measured`, `stale`, `unavailable`) and a nullable unavailable `reason`. Keep existing fields and reset times compatible.
- Reuse the existing Codex rate-limit reader and Claude one-token probe without adding requests; distinguish login/read failures and missing windows without inventing percentages. Preserve older window timestamps during backfill.
- Mark Codex evidence stale at 300 seconds and Claude evidence at 600 seconds (60 seconds for generic other-provider windows); unknown measurement times are stale. Cached evidence retains known provenance and never receives a new observation time.

## Find and resume interactive sessions

- Add exact resolved `cdx history --cwd PATH` and `--interactive` filters before the result limit, preserving the JSON envelope and period/summary support.
- Record interactive launches immediately, update the same row on exit, expose active older runtimes and support `cdx start <name>` through the named launch path, including tmux.
- Prefer exact Claude session IDs and unique project/time-scoped Codex transcript metadata; expose ambiguous recency as unverified. Recover clean, redacted `first_user_prompt` text past provider wrappers, reminders, tools and bare file paths.
- Cover filter ordering, live history, completion/failure deduplication, legacy launch arguments, transcript identity ambiguity, missing evidence and prompt cleanup.

## Conversation tail pagination (planned for 0.26.2)

- Add `cdx conversation --tail N` (1–1000), chronological backward pages via `before_cursor` and `--before`, and a compatible `next_cursor` for live polling. Read JSONL backwards in bounded 64 KiB blocks, preserve normalization, redaction, stable IDs and oversized-record skipping, and reject stale backward cursors.
- Measure tail I/O on 6,000-entry Codex and Claude-compatible transcripts and cover backward traversal, content-block splits, append polling and incomplete/oversized records.

## Read past oversized conversation records

- Skip JSONL records larger than 1 MiB using bounded reads instead of returning `record_too_large`. Emit a short placeholder with a stable ID and the role from readable structural metadata, falling back to `tool`, then advance the cursor so subsequent messages remain accessible. Never return image or attachment bodies.
- Retry oversized trailing records without a newline on the next poll. The 8 MiB page scan budget finishes the current record before returning.
- Bound the cursor's recent tool-name cache to 2 KiB of compact JSON, evicting oldest entries while keeping version-1 cursors with up to 100 names readable.
- Cover 20 MiB records in the middle, cursors immediately before them, incomplete oversized tails, bounded reads, stable IDs, conservative role detection and legacy cursor compatibility.

## Preserve interactive conversations across headless runs

- Keep fresh Claude run identities in run records and history without changing the profile's interactive conversation. Skip interactive Codex identity observation when recording headless run history, including detached, remote and continued runs.
- Let `cdx conversation` fall back to the latest local transcript when a profile's recorded ID has no transcript on this host. Explicit `--conversation` lookups remain exact and never fall back. Report `resolution_method` as `conversation_id`, `recency`, or `null`.
- Cover a remote Claude run followed by local interactive conversation reading, local/continued run identity preservation, missing recorded IDs and missing explicit IDs.

## Antigravity quota and run usage

- Install a local Antigravity statusLine command in new profiles and on interactive launch, merging settings and relaying the original stdin to any existing command so its output is preserved. Store only the reading time, plan tier and allowlisted quota fields in an atomic mode-600 profile file; never access Google internal endpoints or antigravity-oauth-token.
- Show Gemini 5-hour and weekly remaining quota, reset times and reading age in status. Include all bucket names, including third-party buckets, in JSON. Mark readings older than 24 hours stale and suppress availability after a bucket's reset has passed.
- Launch headless Antigravity with `agy -p --output-format json` and record its input, output, thinking, cache-read and reported total counters. Preserve the native total without assuming an undocumented cache or thinking subset relationship. Interactive quota is not per-run token usage.
- Cover synthetic native payloads, missing/unknown buckets, stale and expired readings, settings merges, existing command output, private file permissions and headless observation.

## Worker-owned Antigravity headless runs

- Allow Antigravity profiles in remote runs with mandatory bubblewrap, explicit `agy -p --output-format json`, an owner-only worker token mounted read-only, and a volatile HOME. Never transport worker credentials to the controller; redact worker output before SSH forwarding. Hold a worker token lock across each attempt and disable automatic CLI updates.
- Restrict inference to a conservative Google endpoint allowlist plus public DNS, including when tool network access is requested; retain private-range denial. The candidate list and read-only token policy require the live measurements documented in the mission fragment before claiming production acceptance.
- Fail on absent/unsafe worker login, expired sessions, missing/non-success JSON status and refused actions. Normalize JSON usage through `run_usage` and preserve existing run artifacts/history. Cover fake worker success, refusal, expiry, secret redaction, locking, cleanup, local profile authentication and mount/network construction.

## Remote Claude headless runs

- Add `cdx auth claude-token <profile>` to store a dedicated `claude setup-token` value from stdin in a controller-only mode-600 profile file. Missing or unsafe tokens stop remote runs with this command as the remedy; worker login is unnecessary.
- Allow remote Claude JSON headless execution with mandatory bubblewrap isolation, a fresh memory-backed HOME per attempt and no local profile mounts. Carry the token through SSH stdin and a sandbox stdin exec shim, exposing it only in Claude's environment, never worker credential files, argv or persisted output. Keep subprocess environment scrubbing, remove competing authentication/cloud/proxy sources, disable non-essential traffic and refuse `--bare`.
- Allow inference HTTPS to resolved `api.anthropic.com` addresses and DNS by default; retain public tool-network access only when requested. Cover fake-worker usage parsing, output redaction, absent/unsafe token files, stdin storage, isolation construction and volatile cleanup after success, failure and timeout.

## Isolated mission Git and RTK

- Give local and remote isolated linked worktrees a read-only Git view with their own HEAD/index and shared objects/refs, without traversing private host parents or exposing repository/global configuration, hooks, SSH keys or Git push credentials. Preserve supervisor-owned commits and pushes.
- Add the mounted operator `~/.local/bin` to sandbox PATH and persist RTK savings in the execution host's shared cache at `/cache/rtk/history.db`, overriding inaccessible host history paths for isolated launches only.
- Cover real Git commands against selected metadata, local and shipped worker launch environments, and an opt-in required bubblewrap acceptance check for Git, RTK history writes, review mode and an unreadable synthetic SSH key. Document the namespace requirement and sandbox history location.

## Truthful workstation updates

- Keep a zero-exit `agy update` successful when no expected newer CLI version is known, even if its installed version does not advance and its output cannot confirm currency. Preserve `status: unknown` and `latest_version: null`, expose an `update_unverified` warning in JSON and text, and continue failing non-zero updater exits. No additional version source is assumed.
- Stop querying the editor release feed for the Antigravity CLI: its versions do not match `agy`. Keep `latest_version: null` and `status: unknown`, while still running the native `agy update` with `--yes` or confirmation. No read-only latest-version check is documented by `agy update --help`.
- Accept a successful native updater's `You are already on the latest version.` message when the installed version is unchanged, or verify a version increase against the published version when known. Preserve updater failures and unknown inventory status. Cover the real Antigravity output line, version increases, failures, and JSON/text uncertainty.

- Detect advertised native updater subcommands in both stdout and stderr; use Antigravity's known `agy update` command directly. Verify the installed CLI version after updating, retain strict verification for providers with a known expected release, and expose before/after versions without hiding major upgrades.
- Fall back from empty or failed Ollama vendor responses (including Linux HTTP 204) to the latest stable `ollama/ollama` GitHub release. Keep Linux updates manual with `update_available`, a null command, and a service-safety reason; never replace a potentially active binary or restart models automatically.

- Verify latest versions from npm, RTK GitHub releases, and Ollama vendor update endpoints with short read-only probes. Report `unknown` on unavailable evidence; reserve `up_to_date` for identical known versions, including Ponytail revisions.
- Preserve the existing JSON fields and `update_available` status, show uncertainty and manual-update reasons in text, and apply only supported native commands or verified Homebrew package upgrades. Cover matching/outdated versions, source failures, missing tools, and command execution with faked sources.

## Dependency security

- Require cryptography >=50.0.0 for encrypted auth bundles and remove the vulnerable 47.0.0 lock entry. Python 3.9 remains supported from 3.9.2, as cryptography 50 excludes 3.9.0 and 3.9.1.
- Require pytest >=9.0.3 in the development extra on Python >=3.10; retain the existing 9.2.0 lock entry. pytest is not a runtime dependency. Python 3.9 still uses 8.4.2, the last compatible release, and its medium-severity alert remains unresolved pending an upstream backport or a decision to drop Python 3.9 development support.
- Check lock consistency and run the CI test matrix against locked development dependencies without upgrading unrelated packages.

## Run costs and budgets

- Add nullable `cost_usd` to JSON history entries using the same observed usage, model pricing, and price overrides as stats.
- Add `cdx run --budget USD` to stop on measured estimated spend with exit code 125, `budget_exceeded`, and `error.spent_usd` in the final JSON. Share the budget across recovery attempts and failover; support detached runs and fresh budgets for continued runs without charging earlier turns.
- Document unknown usage/prices and delayed provider reporting, including possible budget overshoot. Cover pricing, unknown costs, validation, live process termination, Claude transcript accumulation, continuation boundaries, and detached supervision in tests.

## Remote run cost observations

- Use the local exact-thread observation reader, usage normalization and 128 MiB rollout limit on workers; return content-free model/counter evidence before volatile storage cleanup and bind it to controller run/attempt artifacts.
- Separate supervisor evidence frames from provider stdout, and check live rollout measurements before `turn.completed` so measured remote budget excess still stops the provider. Never price from requested models or controller-side rollouts.
- Preserve the documented fail-closed budget guarantee: measured but unpriceable remote usage exits 125 with `budget_unverifiable`, including after provider completion. Keep provider output in artifacts; completed runs without a budget retain their actual status and unknown cost. Credential snapshots, redaction, cleanup and workspace isolation remain unchanged.
- Cover priced remote/isolated runs, Windows transport, rollouts over 16 MiB, live budget stops, missing/inconsistent/mixed model evidence, unknown prices and completion without pricing using the fake transport.

## Remote Codex runs

- Add `cdx run --remote SSH_TARGET` with controller-owned supervision, registry, history, output, costs, budgets and detached execution.
- Refresh under the controller authentication lock at the seven-day/24-hour thresholds, then send a temporary OAuth credential over SSH stdin with an empty refresh token. Refuse rotating credentials, other providers and CLI version mismatches.
- Keep worker credentials in a private memory-backed home, clean up after success, failure and stop, and sweep dead homes on the next launch. Keep agent stdin separate from bootstrap input and report credential expiration without retrying.
- Cover transport and credential isolation, thresholds, cleanup, sweep, unreachable workers, provider refusal and registry reports with a fake SSH worker.

## Remote worker transport and isolation preflight

- Add `--remote-prefix` for Windows SSH landings such as `wsl.exe -d Ubuntu --`, including detached runs. Keep the POSIX default and use a short double-quoted bootstrap on argv; send framed worker/sandbox source and then credentials/payload over stdin.
- Probe the local bubblewrap/pasta/nftables isolation mechanism on the worker with dummy credentials, including namespace/network startup. Refuse missing dependencies or setup failures without falling back to an unisolated run.
- Enable remote isolated Codex execution after a successful isolation probe, following the operator decision of 2026-11-01. Agent tools can read the copied access token (up to ten days of validity); missing dependencies still refuse without fallback.
- Release the controller authentication lock after preparing the credential snapshot so scheduled authentication refresh can run during long remote missions. Keep profile mission exclusion in the run registry and the worker credential's original expiry.
- Test cmd.exe length/quoting enforcement, Windows prefixes, large stdin payloads, POSIX transport, sanitized credential snapshots, sandbox construction/dependencies and concurrent scheduled refresh with synthetic credentials.

## Isolated Codex credentials

- Replace the local full-profile auth mount with a mode-600 run-private snapshot on verified memory-backed storage, containing an empty refresh token. Refresh on the controller under the auth lock at the existing seven-day/24-hour thresholds before launch.
- Keep snapshots independent of controller refresh during long missions, prohibit authentication writeback, enforce their original expiry, and remove temporary storage after success, failure and stop. Non-isolated local authentication remains unchanged.
- Reject rotating credentials at the sandbox boundary. Test snapshot contents, permissions, cleanup, refresh lock ownership, concurrent controller refresh, remote isolation through fake SSH and missing dependency refusal.
- The separately maintained example-project `scripts/workspace_sandbox.py` requires the same credential guard and run-private lifecycle integration; it is not shipped by this repository.

## Remote Ollama text generation

- Allow Ollama profiles in `cdx run --remote` with an explicitly selected, already installed local worker model and no authentication or Ollama/Codex CLI requirement. Read prompts on the launching host and use the HTTP capability/chat APIs with `stream: false`; retain generated text and prompt/evaluation token counters in run results and usage.
- Add a worker-supervised private Unix socket relay restricted to the fixed `127.0.0.1:11434` destination, selected model, `/api/show` and non-streaming `/api/chat`. Refuse model management, alternate destinations and cloud-backed models. Isolated clients have no network access and mount neither Ollama profiles nor model files; their checkout is read-only.
- State in CLI help and results that this is text generation, not an autonomous coding agent, with no repository edits. Cover success, usage, controller prompt content, missing models, forbidden relay calls, unreachable servers and sandbox relay construction with a fake HTTP API.
