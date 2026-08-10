# CDX Manager 0.18.0

## Features

### An optional desktop tray companion

A native menu bar companion now shows remaining quota across every enabled
session without a terminal open. It is optional, off until installed, and adds
nothing to the quota pipeline: it reads the status CDX already stores through
`cdx tray status --json`.

`cdx tray` gained `status`, `install`, `launch`, `uninstall`, `autostart`,
`doctor`, `events`, `ack`, and `heartbeat`.

The polling is cached by default and never probes a provider on a timer. A live
probe serializes on the Codex auth lock, which an interactive session holds for
its whole run, and races a rotating OAuth refresh token. Only an explicit
refresh — a user gesture from the menu — probes, and the menu says so when a
running session makes refreshing pointless.

Freshness is reported rather than hidden. Each session reads `fresh`, `stale`,
`auth_locked`, or `unknown`, and a figure is never invented for a state that
knows nothing.

### Agent alerts delivered through the tray

When a companion is running, an agent finishing a turn raises one notification
from the tray instead of two from the tray and the direct path. The tray keeps a
bounded list of recent alerts and marks new ones beside the icon for 45 seconds.

Delivery falls back to the previous direct path whenever a companion is absent,
stale, or speaks a schema this CDX does not, so upgrading one side never leaves
the other silent.

On macOS the alert is posted from the signed CDX bundle, so it carries the CDX
name and icon and can be turned off under CDX in System Settings. On Windows it
goes out under CDX's own AppUserModelID once `cdx tray install` has written the
Start Menu shortcut, and under PowerShell's identifier until then.

### Setup hints in `cdx` and `cdx status`

Both commands may end with one dim line pointing at an optional surface not yet
set up — the tray companion, or agent alerts. One hint per invocation, not again
for six hours, retired for good after three showings, never in `--json`, never
alongside an update notice, and `CDX_NO_HINTS=1` turns them off.

## Platform support

- **macOS**: signed bundle, menu bar item, native notifications, LaunchAgent
  autostart.
- **Windows**: taskbar icon that picks its glyph tint from the taskbar theme,
  promotes itself out of the notification overflow once, and reads CDX from WSL
  through interop with no X server and no localhost.
- **Linux**: StatusNotifierItem through ksni, resolved at runtime by looking for
  `org.kde.StatusNotifierWatcher` rather than by matching a distribution name. A
  desktop without one is told so instead of being left with an invisible icon.
  The asset is statically linked against musl, so there is no glibc version to
  match and no gtk, libxdo, or appindicator package to install.

## Trust model

`cdx tray install` fetches a release asset and verifies its published SHA-256
before a single byte is unpacked. The macOS bundle is self-signed: that
signature exists because Apple Silicon refuses to execute unsigned arm64 code,
not because Apple reviewed anything, and the published checksum is what vouches
for the asset. Installing through CDX is also what keeps the file free of the
macOS quarantine attribute and the Windows Mark of the Web, which is why no
browser download link is published.

An update downloads, verifies, and proves the replacement starts before the
working companion is touched. A failure leaves the previous one running, and
`cdx tray doctor` names the interrupted state.

## Validation

- `npm run lint`
- `npm test` — 766 Python tests
- `cargo test` — 45 Rust tests; `cargo clippy` clean with zero warnings on
  aarch64-apple-darwin, x86_64-pc-windows-msvc, and x86_64-unknown-linux-gnu
- `scripts/tray-smoke.sh` on three hosts: macOS arm64 native, Windows serving
  CDX through Ubuntu WSL, and Linux natively in that same WSL
- `logics-manager lint` and `logics-manager audit`
