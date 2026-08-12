# Testing tray changes locally

How to see a tray change working on a development machine, from the cheapest
loop to the one that puts a real icon in the menu bar. Every command here was
run on macOS (Apple Silicon); the notes say where another platform differs.

The ordering is the point: three of the four loops need no install, no signing,
and no interference with the companion already running. Reach for the last one
only when the change is something only a drawn menu can show.

## Prerequisite

A Rust toolchain, once:

```bash
rustup default stable        # nothing below builds without this
```

`cargo` alone is not enough — `rustup` with no default toolchain fails with
"could not choose a version of cargo to run", which reads like a broken install
and is not one.

Python needs nothing: the repository runs from `./bin/cdx`.

## 1. CDX side only — no Rust at all

Anything that changes what CDX publishes (the snapshot, `cdx tray …` commands,
the alert payload) is testable without building the companion:

```bash
./bin/cdx tray status --json | head -40      # the whole snapshot contract
./bin/cdx tray terminal                      # one preference, read back
python3 -m pytest test/test_tray_*.py test/test_notify_py.py -q
```

`./bin/cdx` is the working tree, not the installed CDX. Use it deliberately:
`cdx` on the PATH is the released build and will not show your change.

## 2. The menu, rendered to stdout

The companion draws its whole menu to the terminal with `--print`, which is the
loop to live in. First build is around 25 seconds, every one after is instant.

```bash
CDX_TRAY_CDX="$PWD/bin/cdx" cargo run -q --manifest-path tray/Cargo.toml -- --print
```

`CDX_TRAY_CDX` is what points the companion at the working tree instead of the
installed CDX. Without it you are testing the released behaviour with a
development menu, which looks like it works and proves nothing.

Submenus are rendered indented, checks as `(•)`, disabled actions as `[ ]`, so
the output covers everything a drawn menu shows.

Safe to run while the real companion is running: `--print` reads the spool but
neither heartbeats nor acknowledges, so it cannot steal an alert from the tray
that is actually delivering them.

## 3. The test suites

```bash
cargo test -q --manifest-path tray/Cargo.toml       # 89 tests, well under a second
python3 -m pytest test/ -q
```

The Rust suite covers the menu, the snapshot reader, the spool and the unread
badge — everything except the platform backends, which have no headless test and
are the reason loop 4 exists.

## 4. A real icon in the menu bar

Only for what the first three cannot show: the drawn cell, the notification
banner, the click paths, the icon itself.

```bash
./scripts/build-tray.sh --dev        # writes tray/target/release/CDX.app
```

The companion is single-instance — a pid lock in `TMPDIR` — so the development
build will not start while the installed one holds it. Quit the installed
companion from its own menu first, then:

```bash
CDX_TRAY_CDX="$PWD/bin/cdx" open -n tray/target/release/CDX.app
```

To go back to the installed companion afterwards:

```bash
cdx tray launch                      # stops whatever is running, starts the installed one
cdx tray doctor                      # confirms which one is running, and against which CDX
```

`--dev` is signed ad-hoc, so **its identity changes at every rebuild**. Two
consequences: macOS forgets the notification authorization each time, and the
banner loses the app's own icon. Anything about notification *appearance* has to
be tested with a real signed build (`CDX_TRAY_SIGN_IDENTITY=… ./scripts/build-tray.sh`).
`--dev` refuses `--package` outright, and nothing built this way should ever be
distributed. See `adr_005`.

## Firing an alert without waiting for an agent

The whole notification chain — hook, privacy filter, spool, companion, banner —
in one command:

```bash
echo '{"hook_event_name":"Stop","cwd":"'"$PWD"'","last_assistant_message":"Smoke test."}' \
  | CDX_SESSION_NAME=runbook CDX_NOTIFY_PREVIEW=1 ./bin/cdx notify
tail -1 "${CDX_HOME:-$HOME/.cdx}/tray/events.jsonl"      # what the companion was handed
```

Swap `hook_event_name` for `StopFailure` (add `"error_type"`, `"error_message"`)
or `PermissionRequest` (add `"tool_name"`, `"tool_input"`) to exercise the other
two alert shapes. Drop `CDX_NOTIFY_PREVIEW=1` to see what a session without
response previews shows.

This writes a real line to the spool and raises a real banner. Harmless, but it
is not a dry run.

## Testing against a store that is not yours

To exercise the menu without touching real sessions:

```bash
export CDX_HOME=/tmp/cdx-dev
./bin/cdx tray status --json                 # empty store: icon "unknown", reason "no_sessions"
cp ~/.cdx/sessions.json "$CDX_HOME/"         # or copy real rows in for a realistic menu
```

`CDX_HOME` is read by every CDX path, including `cdx notify`, so the isolated
store gets its own spool and its own preferences.

## Checking what is actually installed

```bash
cdx tray doctor
```

It names the installed companion, whether it is running and under which pid,
which `cdx` binary that companion calls, and whether the hook store the
notification path writes to is the one the companion reads. A tray that receives
no alert while everything looks fine is almost always a `hook_store` mismatch.
