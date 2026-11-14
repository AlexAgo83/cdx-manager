# Operations

## Backup And Restore

You can move sessions between machines with portable bundles:

```bash
cdx export backup.cdx
cdx import backup.cdx
```

To migrate auth and avoid logging in again, include auth data in an encrypted bundle:

```bash
export CDX_BUNDLE_PASSPHRASE='choose-a-strong-passphrase'
cdx export backup-auth.cdx --include-auth --passphrase-env CDX_BUNDLE_PASSPHRASE
cdx import backup-auth.cdx --passphrase-env CDX_BUNDLE_PASSPHRASE
```

Notes:

- `--include-auth` is encrypted, requires a passphrase, and exports only provider credential files rather than full profile caches, logs, or installed plugins.
- Keychain-backed Claude authentication cannot currently be exported. If any selected profile uses it, `--include-auth` exits non-zero before writing anything, including with `--force`; text and JSON errors identify the affected profiles. Export without `--include-auth` and log in after import, or select only profiles whose authentication is file-backed. An inaccessible keychain is an explicit error, not a successful incomplete export.
- Merge imports snapshot each existing profile before modification, preserving symlinks instead of following them. This temporarily needs space for a second copy of that profile. On failure, CDX restores the original files, record and state; if recovery also fails, the error gives the retained recovery directory containing the original metadata and any remaining profile snapshot.
- Without `--passphrase-env`, `cdx` prompts in an interactive terminal. Non-interactive callers can pass `--passphrase-stdin` to read the passphrase from stdin (one line) instead of exposing it in the child environment.
- `--sessions work,perso` exports or imports only a subset.
- `--force` allows overwriting existing destination sessions during import or replacing an existing bundle file during export. Import preserves detected local `plugins/` state when the bundle does not provide it, and refuses to overwrite existing sessions from a bundle without auth payloads unless `--allow-authless-force` is also passed.
- Import only writes the provider credential files listed above, and only from an encrypted `--include-auth` bundle; any other file in a bundle makes the import fail before anything changes.
- Import refuses a new session whose `profiles/<name>` folder already exists without a registered session; remove or rename the folder first (`cdx repair` lists orphan profiles).
- `--force` on a Claude session always replaces its login: the profile's keychain entry is removed even when the bundle carries no credential, and restored if the import fails.
- Auth bundles contain credentials. Treat them like secrets and delete them after transfer.

## Release checklist

- Name the GitHub Release exactly as its tag, `vX.Y.Z` (for example, `v0.21.1`); use the checked-in versioned changelog for its notes.
- Before publishing npm or PyPI packages, run `npm run release:validate`.
- The release tag must match `package.json`, `pyproject.toml`, `src/cli.py`, and `VERSION`.
- `checksums/release-archives.json` must include the matching `vX.Y.Z` entry with both `github_tarball_sha256` and `github_zip_sha256`.
- Publishing a GitHub Release runs the checksum upload workflow: it regenerates `checksums/release-archives.json` for the release tag and uploads it as the `release-archives.json` asset with replacement enabled for safe reruns.
- If the asset is missing or stale, repair it with `python3 scripts/update_release_checksums.py --tag vX.Y.Z`, then `gh release upload vX.Y.Z checksums/release-archives.json --clobber`.
- Publish packages only after the checksum workflow succeeds and `npm run release:validate`, `npm run lint`, and `npm test` pass.

## Available Scripts

- `npm test`: run the Python test suite with `pytest`
- `npm run test:py`: run `pytest` through the portable launcher
- `npm run test:coverage`: run `pytest` with terminal coverage reporting for `src/`
- `npm run lint`: check project guidance, the Node launcher, `ruff`, and byte-compile the Python sources, scripts, and tests
- `npm run release:validate`: verify version alignment and required GitHub release archive checksum metadata before publication
- `npm run link`: link `cdx` globally for local development (`npm link`)
- `npm run unlink`: remove the global link

## Windows Support

- Supported install paths on Windows:
  - `npm install -g cdx-manager`
  - `pipx install cdx-manager`
  - `uv tool install cdx-manager`
  - `install.ps1`
- The npm launcher resolves Python via `py -3`, `python`, then `python3`, so a global npm install works even when `python3.exe` is missing.
- `install.sh` is Unix-only.
- `make install` and `make uninstall` are Unix-oriented convenience commands, not the default Windows path.
- `cdx` isolates Claude sessions on Windows by setting `HOME`, `USERPROFILE`, `HOMEDRIVE`, and `HOMEPATH`.
- Desktop notifications use PowerShell on Windows.
- Codex transcript capture is optional on Windows:
  - if a compatible `script` command is available and exposed via `CDX_SCRIPT_BIN`, `cdx` uses it
  - otherwise Codex launches without transcript capture and the session still works normally
- `cdx doctor` reports the transcript-capture fallback explicitly so missing `script` on Windows is visible without being treated as a hard failure.
- `cdx doctor --json` includes detected `codex --version` and `claude --version` output when available, plus conservative capability hints for recent provider memory, model, and headless diagnostic surfaces. These hints are informational; `cdx` does not edit provider-private memory stores.

## Disk maintenance

Use `cdx disk` for a total `CDX_HOME` measurement, and `cdx disk profiles` for the `profiles/` total plus a per-profile breakdown.

In an interactive terminal, long scans report their current stage and per-profile progress on stderr. JSON and redirected output remain free of progress messages.

Text output uses aligned summary tables with profile size, share of total space, and reclaimable space. Candidate details are grouped by profile with separate size, type, risk, and evidence columns.

```bash
cdx disk
cdx disk profiles
```

To find cleanup candidates without deleting anything:

```bash
cdx disk profiles --candidates
cdx disk profiles --candidates --json
```

Candidate evidence includes profile name, path, size, risk, reason, and metadata such as modified time or old-log file counts. The current cleanup candidates are intentionally limited to:

- temporary marketplace/plugin staging caches under `profiles/*/.tmp/`
- `.log` files older than the requested age inside profile `log/` directories

`cdx` also runs a passive disk cleanup check at most once per day on advisory commands such as `cdx` and `cdx status`. It writes the check timestamp and latest measurements to `~/.cdx/state/disk-cleanup-check.json`. A warning is shown only when at least one threshold is met:

- `CDX_HOME` uses 10 GB or more
- cleanup candidates can reclaim 1 GB or more
- temporary cache candidates can reclaim 500 MB or more
- old log candidates can reclaim 500 MB or more
- one profile is 2 GB or more, or one profile is at least 25% of `profiles/` when `profiles/` is already 1 GB or more

The passive warning is read-only and points to `cdx disk profiles --candidates`; it never deletes files.

Apply cleanup only with explicit actions:

```bash
cdx clean profiles --tmp
cdx clean profiles --old-logs 30d
```

`--tmp` removes temporary marketplace/plugin clone/backup staging directories. `--old-logs 30d` removes only `.log` files older than 30 days. The commands do not remove `auth.json`, `config.toml`, `sessions/`, SQLite state, installed `plugins/`, `skills/`, or credentials.

All `cdx clean` actions require interactive confirmation before any deletion or log truncation begins. Non-interactive scripts must pass `--yes` explicitly.

The cleanup action is selected only when `--tmp` or `--old-logs` is present. This keeps `cdx clean profiles` available for an existing session named `profiles`. If any candidate or old log cannot be removed, cleanup stops with a non-zero error that identifies the affected path; it does not report the operation as successful.

## When an account runs out

A conversation that hits a 5-hour or weekly limit can go on under another account.

1. Keep accounts you share or want to spare out of every automatic choice:
   `cdx set shared --policy ask-first` (offered only with a typed confirmation),
   `cdx set colleague --policy never` (never offered).
   Before it happens, `cdx status <name>` shows `Runs out: ~HH:MM at this pace` when the
   current pace empties the account before its reset: a good moment to move long work.
2. When a session stops on its limit, check the plan first:
   `cdx rescue --dry-run` shows the stopped conversation, its folder, when the
   account comes back, and the account that would take over.
3. Run `cdx rescue` and confirm. It runs `cdx handoff <source> <target>
   --source-conversation <id>` in the folder the conversation last ran in; the new
   session starts with a recovery prompt over the exact transcript. A successful
   handoff stamps the source conversation `rescuedAt`, so `cdx rescue` does not
   offer it again until that session is launched again.
4. Several stopped sessions: `cdx rescue <session>` picks one; `--to <account>`
   forces the target.

Limits: only conversations launched in the last 24 hours, on an account at 0% or whose
transcript ends on the usage-limit error (caught before `cdx status` refreshes).
The automatic pick only takes a ready account of the same provider; `--to` checks
only that the account exists and its policy is not `never`, so a target of another
provider or without quota is yours to rule out. If nothing is ready,
`cdx status` shows when each account resets.

## Delegating work in the background

Hand a task to a background run and keep working, without starting more runs than your accounts can carry.

1. Set a cap once, in your shell profile: `export CDX_MAX_RUNS=2`. Every `cdx run` then refuses to
   start a third concurrent run (`too_many_runs`) instead of piling work onto spent accounts. `0` or a
   negative value means no limit. A refused run leaves the session untouched (no new conversation).
2. Start the run with a label you will recognise later:
   ```bash
   cdx run --provider claude --cwd ~/Documents/cts --label "fix build cts" \
     --prompt-file task.md --detach --json
   ```
3. Follow it: `cdx runs --json` lists runs with their label and status; `cdx run-status <run_id> --json`
   and `cdx run-tail <run_id> --json` show one of them.
4. A run refused by the cap: wait for one to finish, or pass `--max-parallel N` for that run.
## Starting a session on a task in another repository

From a hub session or a terminal, open a session in another repository with the task and
what you already approve, so it neither stops too early nor goes further than you meant:

```bash
cdx work --dir ~/Documents/cts --task "Fix the failing CI on main" \
  --end-state "CI green on a pull request, merged"
```

- Write the end state as the result you will accept, naming the steps it includes (commit, push,
  PR, merge). A vague "show me first" makes the session stop after the commit and wait for a push.
- Leave `--end-state` out when you want to review before anything is published: the session then
  stops before any commit, push or PR.
- Name the repository's skill in the task when one fits ("use the implement-task skill") instead of
  restating its steps; the session is told to read the repository's instructions anyway.

## Session retros

A correction you make once should not have to be made again next session.

1. Turn retros on for the accounts you work with: `cdx set work --retro on` (off by default:
   each retro is one model call).
2. When an interactive session with at least 3 prompts ends, cdx starts a detached
   `cdx run --kind retro --permission read-only --power low` on a ready `use` account of the
   same provider. It reads the session's transcript and writes nothing.
3. Read the reports with `cdx retro` (or `cdx retro --limit 10`). Each lists the corrections you
   made, then lessons tagged `memory:`, `runbook:`, `skill:` or `CLAUDE.md:` with the text to add.
4. Apply the ones you agree with yourself, or ask the next session to. With
   `--shared-memory on`, a lesson saved to memory reaches every account.

Retro runs also appear in `cdx runs`; a retro never triggers a retro of its own.

## Banked Codex resets

Eligible Codex accounts expose manually redeemable rate-limit resets through the Codex app-server. `cdx status` shows their available count in the `RESETS` column; `cdx status <name>` also shows the nearest known expiration, and JSON status includes the available reset details supplied by Codex.

Activation is always explicit:

```bash
cdx reset <name>
cdx reset <name> --yes --json
```

Without `--yes`, an interactive confirmation is required. `cdx` sends an idempotency key, consumes at most one available reset, and refreshes the session status after a successful activation. It never activates a reset from `cdx status` or any background check.

## Troubleshooting

### Codex credential refresh

`cdx auth refresh work` makes a provider-native, non-generation request for one
managed Codex profile. It can refresh an expiring access token, but never starts
an agent or submits a prompt. Use `cdx auth refresh all --json` when a scheduler
needs a stable result; CDX never installs or enables that scheduler for you.

For example, a user-owned daily cron entry can run:

```sh
0 6 * * * cdx auth refresh all --json
```

`locked` means an interactive session owns the profile refresh lock and was left
untouched. If every selected profile is locked, the command is non-zero because
it verified no credential; a mix of valid and locked profiles remains successful.
Bulk refresh skips disabled profiles, while `cdx auth refresh <name>` still lets
an operator inspect one explicitly. `login_required` means the provider rejected
the local refresh token; run the supplied `cdx login <name>` command interactively.
Hosts keep independent rotating credentials, so copying an auth file is not ongoing
credential sync.

- **`cdx <name>` fails with "not authenticated"** — run `cdx login <name>` first. `cdx doctor` uses the same Codex app-server probe as `cdx auth refresh`, so a local auth file alone is never reported as live authentication; a rejected refresh token is reported as `login_required` with the matching login command.
- **A Claude session has no claude.ai connectors (Microsoft 365, ...) in `/mcp`** — `cdx login <name>` stores a setup-token for Claude profiles, and Claude Code can only make model requests with it: it never loads claude.ai connectors. `cdx status` shows each Claude profile's auth type (`setup-token` or `full-login`; `auth_type` in `--json`). To switch, start the session and run `/login` inside it. Once the profile holds its own claude.ai login (its `.claude/.credentials.json`, or its profile-specific `Claude Code-credentials-<hash>` keychain entry on macOS), cdx stops passing the setup-token on later launches. If that login later expires, run `/login` again, or go back to a setup-token with `cdx login <name>`, which removes the profile's `/login`.
- **Keep credentials away from what a Claude agent runs** — by default Claude Code passes its credentials, including the setup-token cdx injects, to the Bash commands, hooks and stdio MCP servers it starts. `cdx set <name> --scrub-env on` launches that session with `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, which strips credential-looking variables from those subprocesses (GitHub tokens and proxy settings stay). It is off by default: it also removes other secrets an agent may need (`NPM_TOKEN`, a `DATABASE_URL` with a password), and on Linux it isolates Bash from host processes, so `ps` and `kill` no longer see them. For unattended sessions that read untrusted content, enable it only with explicit tool permissions: Claude forces its default permission mode when scrubbing is enabled, even if cdx requests `--permission full`. In headless runs, tools that require approval are denied unless explicitly allowed. For example, `cdx set <name> --scrub-env on --extra-args '--allowedTools "Read" "Bash(pwd)"'` allows those tools; adapt the allowlist to the task. cdx keeps scrubbing enabled and reports structured `permission_denials` as a run warning, without turning a successful provider exit into a failure: a denied tool can be replaced successfully.
- **An agent stops on "Do you trust this folder?" or Codex's "Hooks need review"**: cdx answers both before the provider starts, through two launch settings that are on by default and can be turned off independently. Before every launch, resume, handoff, provider background run and headless run that uses the profile home, `cdx set <name> --auto-trust-folder on|off` records trust for the working folder (as given and resolved, when they differ) in that profile's own config: Claude Code `projects[<folder>].hasTrustDialogAccepted` in `<home>/.claude.json`, Codex `[projects."<folder>"] trust_level = "trusted"` in `config.toml`, Antigravity `trustedWorkspaces` in `<home>/.gemini/antigravity-cli/settings.json`. `cdx set <name> --auto-trust-hooks on|off` approves every hook Codex lists as untrusted or modified, cdx's own notification hooks included, as `[hooks.state."<key>"] trusted_hash` in `config.toml`; the hashes come from Codex's app-server `hooks/list` and are written through its `config/batchWrite`, which costs about a second per Codex launch. Claude Code and Antigravity have no separate hook review: their hooks follow folder trust. Writes merge, keep every other setting and happen only when something is missing. Isolated and remote runs start from a fresh home and write nothing. With both on, a repository's own hooks and settings run without review: turn them off for sessions that open untrusted code. A file cdx cannot parse is left alone and the launch prints a warning.
- **Codex stops on "Update available x -> y" at startup**: cdx updates Codex itself (`cdx update all`), so before every Codex launch, resume, handoff and run that uses the profile home it keeps `check_for_update_on_startup = false` in that profile's `config.toml` (written through Codex's app-server, merged like the trust records). `cdx set <name> --codex-update-prompt on` writes `true` instead and brings the screen back; off is the default.
- **Share Claude's memory across accounts** — Claude Code keeps its auto-memory (`.claude/projects/<project>/memory`) in the profile home, so each account starts without what the others learned. `cdx set <name> --shared-memory on` links that folder, for the project being launched, to `~/.cdx/shared-memory/<project>`, shared by every profile with the setting on. Existing memory is copied in and the old folder kept as `memory.pre-cdx-<time>`; `MEMORY.md` indexes are merged line by line. A file with the same name and different content on two accounts is a conflict: cdx leaves that profile alone and names the files to merge by hand. macOS and Linux only (symlinks).
- **One of two Codex accounts keeps asking for login** — run `cdx doctor --json` and inspect each Codex session's `codex_auth_file`, `codex_live_auth`, and `codex_stale_auth_logs` checks. If recent logs mention expired auth, repair only that isolated profile with `cdx login <name>`. Codex Business profiles can share the same `tokens.account_id`; `cdx doctor` reports `codex_shared_account_id` as a workspace-level clue, not proof that two profiles use the same user. Newly created sessions seed from the current global `~/.codex/auth.json` when one exists. For two separate Codex accounts, create or repair each session by running `cdx login <name>` for that session; `cdx login` does not log out first, so use `cdx logout <name>` explicitly only when you want to clear that isolated profile.
- **`cdx` says no compatible Python 3.10+ interpreter was found** — install Python 3.10 or newer and make `py -3`, `python`, or `python3` available on PATH.
- **`cdx add` succeeds but the session does not appear** — check that `CDX_HOME` is consistent between calls; a mismatch creates two separate registries.
- **Status shows `n/a` for all fields** — the Codex app-server rate-limit probe may be unavailable, the session may not be authenticated, and no legacy transcript/history status has been captured yet.
- **`cdx rmv` says "Removal requires confirmation in an interactive terminal"** — pass `--force` to bypass the prompt in non-interactive environments (scripts, CI).
- **`cdx login` hangs** — the provider's login flow requires a browser or device code. Follow the on-screen instructions in the terminal that opened.
- **`make install` says `npm link` is not found** — ensure Node.js and npm are installed and in your PATH.
- **On Windows, `doctor` warns that `script` is missing** — this is expected on many setups. Codex still launches, but transcript capture stays disabled unless you point `CDX_SCRIPT_BIN` to a compatible wrapper.


### Git and RTK in isolated workspaces

Local and remote `cdx run --isolate-workspace` use the same sandbox implementation.
For a linked Git worktree, CDX builds a read-only Git view at `/home/agent/.git`:
the mission's HEAD and index, plus the common objects, refs, packed refs, shallow
boundary and split-index files. `GIT_DIR`, `GIT_COMMON_DIR` and `GIT_WORK_TREE`
select that view without traversing the operator's private home directories.
`git log`, `show`, `diff`, `status`, `blame`, `branch` and `rev-parse` can read
the mission history, including packed objects and refs. Review runs also keep
checkout files read-only. Git metadata stays read-only in writable missions,
as before: committing and pushing remain the supervising mission flow's job.

Host repository configuration, hooks, other worktrees, global Git configuration,
SSH keys, credential helpers and token environment variables are not added.
The view has no configured remotes. Existing provider authentication rules are
unchanged; this does not grant Git push credentials.

The sandbox appends the mounted operator `~/.local/bin` to PATH, including for
noninteractive remote launches whose PATH omits it. An installed `rtk` is thus
available without installing a second copy. Isolated launches override
`RTK_DB_PATH` with `/cache/rtk/history.db`, backed by
`~/.cdx/shared-cache/rtk/history.db` on the execution host. Savings persist
across isolated attempts; the operator's normal RTK history is not mounted.
Inspect them with `RTK_DB_PATH="$HOME/.cdx/shared-cache/rtk/history.db" rtk gain`
on that host. Non-isolated launches keep their normal history selection.

Installed user toolchains stay usable although the box HOME is empty. The
sandbox mounts `~/.local/lib`, `~/.local/share/pipx`, `~/.local/pipx` and
`~/.cargo/bin` read-only, beside the existing `~/.nvm`, `~/.local/bin` and
`~/.local/share/uv` mounts. PATH also gains `~/.cargo/bin` and the newest
`~/.nvm/versions/node/*/bin`, after the launch PATH, and PYTHONPATH lists the
user `~/.local/lib/python*/site-packages` directories so `python3 -m pip` and
user-installed packages resolve. No configuration or credential directory is added.

Run the real confinement acceptance check on a Linux host with bubblewrap and
RTK installed (it uses disposable fixtures and synthetic secrets):

```bash
CDX_REQUIRE_SANDBOX_TESTS=1 python3 -m pytest -q test/test_workspace_sandbox_tools_py.py
```

It exercises the local and shipped worker implementations, writable and review
checkouts, Git history commands, RTK database writes, and denial of a synthetic
SSH key outside the checkout. The required mode fails rather than skipping
when nested namespaces or RTK are unavailable. Default test runs skip only
those unavailable integration cases; copied-metadata Git checks still run.

### Playwright in isolated workspaces

Isolated preparation and provider environments force `PLAYWRIGHT_SKIP_BROWSER_GC=1`.
The browser cache is shared with host services, but package paths differ inside
`/cache` and on the host. Playwright garbage collection cannot see every user's
package references and must not delete other users' browser revisions. Browser
installation remains available; cache cleanup is an explicit operator operation.

## Run Codex or Ollama on an SSH worker

```sh
cdx run work --remote agent@worker --cwd /srv/project --prompt 'Run the checks' --json
cdx run work --remote worker --cwd /srv/project --prompt-file task.txt --detach --label checks --budget 2 --json
cdx run work --remote host-b --remote-prefix 'wsl.exe -d Ubuntu --' --cwd /srv/project --prompt 'Run the checks' --json
```

The controller remains the authority for the profile, quota, history, costs and
run registry. Use `run-status`, `run-report` and `run-tail` on the controller with
the returned run ID. Permission, model, reasoning effort, prompt, timeout, budget,
label and detached execution use the existing run options. `--cwd` names an
absolute directory on the worker; it need not exist on the controller. Files are
not synchronized. Use `--project` to explicitly attribute a remote checkout to a
project. Remote runs do not retry or fail over automatically, including when
`--failover` is supplied.

For Codex: a POSIX controller with `ssh` and Codex on PATH, and a Linux worker
with Python 3, memory-backed `/dev/shm`, and exactly the same `codex --version`.
Configure SSH keys, host trust and aliases in advance; the connection uses batch
mode and bounded connection/keepalive timeouts. Provider refusal, unreachable
workers and version mismatches fail before sending credentials. Codex requires an OAuth
profile. Remote continuation is refused because the temporary home
does not preserve conversation rollouts. Codex's native permission sandbox still
applies to ordinary remote runs.

For SSH servers landing in Windows `cmd.exe` (including Host B and Host C), pass
`--remote-prefix 'wsl.exe -d Ubuntu --'` to enter Linux before starting Python.
The prefix accepts plain command words, options and paths without spaces or shell
metacharacters; it is forwarded to detached runs. POSIX targets need no prefix.
Only a short, double-quoted Python bootstrap is sent in the SSH command line;
the worker and shared sandbox source are framed on stdin before the payload.
Neither source size nor prompt size consumes cmd.exe's 8191-character command limit.

Remote Ollama profiles also support headless text generation:

```bash
cdx run local --remote worker --cwd /srv/project --model qwen3:8b --prompt-file question.txt --isolate-workspace --json
```

Here `local` is an existing Ollama profile. The named model must already be
installed on the worker's unauthenticated `127.0.0.1:11434` Ollama API; CDX
never downloads a missing model and rejects cloud-backed models. The prompt
file is read on the launching host and sent as content over SSH. This path
uses `/api/show` and `/api/chat` with `stream: false`, without an Ollama CLI or
Codex installation. Results identify `execution_mode: "text_generation"` and
include generated text in `result`, plus `prompt_eval_count` / `eval_count`
and normalized input/output token counts in `usage`.

Ollama is not an autonomous coding agent and does not edit the repository.
With `--isolate-workspace`, the checkout is read-only and the client has its
own network namespace without network access, including when `--network-access`
is supplied. A private Unix socket connects it to a supervisor-owned relay
with the fixed loopback destination and only the selected model's capability
and non-streaming inference calls allowed. Pull, delete, push, arbitrary URLs,
proxying and redirects are refused. No `~/.ollama` directory or model files
are mounted. The relay is removed on completion or cancellation. Remote
continuation remains unsupported; an explicit model or profile model is required.

Codex `--remote` supports `--isolate-workspace` using the same local isolation mechanism:
bubblewrap, pasta (passt), nftables, Python, the checkout/toolchain allowlist,
and an actual namespace/network setup using a dummy credential. Missing dependencies,
namespace denial or invalid checkouts fail before sending real credentials, without
an unisolated fallback.

For **every isolated Codex run**, local or remote, the sandbox mounts only a
run-private, mode-600 `auth.json` on verified memory-backed storage, with an empty
`refresh_token`. It never mounts the controller profile's full authentication file.
The controller refreshes under the authentication lock at the thresholds below
before preparing the snapshot, then releases the lock for the run. The temporary
home is removed after success, failure, launch errors and stop. Non-isolated local
runs and interactive login/refresh retain their normal profile authentication.

**Accepted residual risk (operator decision, 2026-11-01):** agent tools inside the
sandbox can read the copied access token, which can remain valid for up to ten
days. A read-only mount prevents modification, not disclosure. The rotating refresh
token never enters the sandbox or leaves the controller. Codex was measured to run
with an empty refresh token on 2026-11-01.

A long isolated Host A mission keeps its original credential snapshot even when
scheduled controller refresh updates the real profile. There is no authentication
writeback or token renewal inside the sandbox. A run that outlives its access token
fails with a clear temporary-credential expiry error and must start a new run.

The controller takes the profile's authentication lock and refreshes through its
local [Codex app-server](https://learn.chatgpt.com/docs/app-server) when `last_refresh` is older than seven days or the access
token has less than 24 hours left. It verifies freshness after refreshing and
fails closed if freshness or expiration cannot be established. Only
`access_token`, `id_token`, `account_id` and `last_refresh` travel, with an empty
`refresh_token`. The rotating refresh token never leaves the controller. The
credential travels exclusively over SSH stdin, and is absent from command
arguments, environment variables, run records and output. The agent receives
`/dev/null` as stdin, not the bootstrap script or credential transport.

Each worker run gets a private mode-700 home under
`/dev/shm/cdx-remote-<uid>/run-*`, with mode-600 `auth.json` and file-only credential storage. Only non-secret scalar
preferences (`model`, `model_reasoning_effort`, `service_tier`, `personality`,
`model_context_window`, `model_auto_compact_token_limit`) from the top level of
`config.toml` are copied. Hooks, custom providers, environment settings and other
controller-local configuration are not copied. The home is removed on completion,
failure, cancellation and SSH stdin closure. Stop a detached run by sending
SIGTERM to the controller PID returned at launch. Uncatchable worker termination
can leave a home behind; the next launch sweeps homes whose worker lock is no
longer held. No persistent worker authentication is installed or refreshed.

A profile occupied by a remote run is busy for local and remote runs using the
same controller through the run registry. The authentication lock is held only
while refreshing and validating the credential snapshot, then released before SSH
launch. Scheduled `cdx auth refresh` and quota probes can acquire it during a long
mission; they no longer see a mission-long `locked`/`auth_refresh_indeterminate`
result. A probe overlapping the short snapshot can still report contention.
Controller renewal does not extend the worker's copied access token; quota remains
one controller-side account snapshot, never a worker copy. Multiple independent controllers sharing copied OAuth profiles are not
supported. Costs and budget checks use measured worker usage and observed rollout
models, using the same exact-thread reader and 128 MiB rollout limit as local
isolated runs. Content-free evidence travels in supervisor frames separated from
provider stdout; raw rollouts and credentials are never returned. Live rollout
counters can stop an over-budget run before `turn.completed`. Unknown prices and
delayed provider reporting retain the usual budget limitations. With `--budget`,
measured but unpriceable usage still fails with `budget_unverifiable` (exit 125),
even after the provider finishes, preserving the documented fail-closed guarantee.
Provider output remains in the run artifacts; without a budget, a completed run
keeps its provider status and unknown cost. A run that outlives the access credential fails with
`remote_credential_expired`, requiring a new controller launch.

The empty-refresh-token behavior was measured with Codex CLI 0.166.0. Real-host
acceptance should verify that the installed matching CLI does not attempt a
refresh with the temporary home, that the controller token chain stays unchanged
for a fresh credential, and that cleanup works after disconnect and SIGTERM.
