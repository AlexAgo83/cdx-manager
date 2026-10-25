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
   session starts with a recovery prompt over the exact transcript.
4. Several stopped sessions: `cdx rescue <session>` picks one; `--to <account>`
   forces the target.

Limits: only conversations launched in the last 24 hours, on an account at 0% or whose
transcript ends on the usage-limit error (caught before `cdx status` refreshes),
and only to an account of the same provider. If nothing is ready,
`cdx status` shows when each account resets.

## Delegating work in the background

Hand a task to a background run and keep working, without starting more runs than your accounts can carry.

1. Set a cap once, in your shell profile: `export CDX_MAX_RUNS=2`. Every `cdx run` then refuses to
   start a third concurrent run (`too_many_runs`) instead of piling work onto spent accounts.
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
- **Keep credentials away from what a Claude agent runs** — by default Claude Code passes its credentials, including the setup-token cdx injects, to the Bash commands, hooks and stdio MCP servers it starts. `cdx set <name> --scrub-env on` launches that session with `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, which strips credential-looking variables from those subprocesses (GitHub tokens and proxy settings stay). It is off by default: it also removes other secrets an agent may need (`NPM_TOKEN`, a `DATABASE_URL` with a password), and on Linux it isolates Bash from host processes, so `ps` and `kill` no longer see them. Worth turning on for unattended sessions that read untrusted content.
- **Share Claude's memory across accounts** — Claude Code keeps its auto-memory (`.claude/projects/<project>/memory`) in the profile home, so each account starts without what the others learned. `cdx set <name> --shared-memory on` links that folder, for the project being launched, to `~/.cdx/shared-memory/<project>`, shared by every profile with the setting on. Existing memory is copied in and the old folder kept as `memory.pre-cdx-<time>`; `MEMORY.md` indexes are merged line by line. A file with the same name and different content on two accounts is a conflict: cdx leaves that profile alone and names the files to merge by hand. macOS and Linux only (symlinks).
- **One of two Codex accounts keeps asking for login** — run `cdx doctor --json` and inspect each Codex session's `codex_auth_file`, `codex_live_auth`, and `codex_stale_auth_logs` checks. If recent logs mention expired auth, repair only that isolated profile with `cdx login <name>`. Codex Business profiles can share the same `tokens.account_id`; `cdx doctor` reports `codex_shared_account_id` as a workspace-level clue, not proof that two profiles use the same user. Newly created sessions seed from the current global `~/.codex/auth.json` when one exists. For two separate Codex accounts, create or repair each session by running `cdx login <name>` for that session; `cdx login` does not log out first, so use `cdx logout <name>` explicitly only when you want to clear that isolated profile.
- **`cdx` says no compatible Python 3 interpreter was found** — install Python 3 and make `py -3`, `python`, or `python3` available on PATH.
- **`cdx add` succeeds but the session does not appear** — check that `CDX_HOME` is consistent between calls; a mismatch creates two separate registries.
- **Status shows `n/a` for all fields** — the Codex app-server rate-limit probe may be unavailable, the session may not be authenticated, and no legacy transcript/history status has been captured yet.
- **`cdx rmv` says "Removal requires confirmation in an interactive terminal"** — pass `--force` to bypass the prompt in non-interactive environments (scripts, CI).
- **`cdx login` hangs** — the provider's login flow requires a browser or device code. Follow the on-screen instructions in the terminal that opened.
- **`make install` says `npm link` is not found** — ensure Node.js and npm are installed and in your PATH.
- **On Windows, `doctor` warns that `script` is missing** — this is expected on many setups. Codex still launches, but transcript capture stays disabled unless you point `CDX_SCRIPT_BIN` to a compatible wrapper.
