# CDX Manager 0.18.4

## Fixes

### Agent alerts arrive when they happen

An alert reached the tray on the next poll, so up to thirty seconds passed
between a turn finishing and the banner appearing — where the direct path had
been instant. The poll period is a cost budget, not a latency target, and it was
the wrong one for the single event a user actively waits for.

The companion now notices the spool changing between polls. No file watcher was
needed: the event loop already wakes five times a second, so a `stat` costs
microseconds at that rate. Measured at 0.57s from hook to consumption, including
the polling in the measurement itself.

Unchanged across the Windows-to-WSL boundary, and deliberately: a Windows
process cannot watch a path inside the Linux filesystem, so the poll period
remains the latency there.

### The menu bar icon stays visible after the first poll

`tray-icon`'s macOS `set_icon` clears the template flag unconditionally, so every
refresh dropped the setting that lets macOS invert the glyph for the current
theme. The icon started white and turned black about thirty seconds later, which
on a dark menu bar means invisible.

### `cdx update` brings the tray companion with it

The companion is a separate artifact on a separate release, so it drifted and
had to be reinstalled by hand. `cdx update` now moves it too, through the staged
path that verifies the asset and proves the replacement starts before the
working one is touched — and never fails the update if it cannot: the previous
companion stays installed and the reason is reported.

`cdx tray doctor` names the state now, rather than printing two version numbers
and leaving the comparison to you: `aligned` or `drifted`.

## Features

### The menu is readable at a dozen accounts

Rows are selectable rather than informational — macOS renders disabled items
grey, so a dozen arrived as a wall of grey text — and clicking one opens a
terminal on that session. The list is sorted by urgency, most constrained first;
it previously arrived in storage order, so an account at 1% could sit tenth
while the icon showed critical.

Sessions are grouped under their provider instead of repeating it on every row,
and each carries a gauge. On macOS the rows are drawn: name, a gauge coloured by
severity, and the figure aligned on a fixed column — a native menu font is
proportional, so text alone cannot align. Windows and Linux keep the text rows,
which say everything the drawing does.

Times are distances, not stamps: `↻ in 6d 23h` rather than `↻ Aug 18 03:23`, and
a stale row says how stale. The wording is `cdx status`'s own.

### A switch to silence agent alerts

In the tray menu and as `cdx tray alerts on|off|status`. Muting stops the
banner, not the record — events keep reaching a running companion, so the menu
shows what you missed — and it applies to the direct path too, so quitting the
tray does not silently un-mute you.

### `cdx tray install` starts what it installed

And asks whether to launch it at login. `--yes` answers without a prompt,
`--no-autostart` declines, and a non-interactive run declines too: a script must
not acquire a startup entry by running an install.

## Validation

- `npm run lint`, `npm test` — 790 Python tests
- `cargo test` — 52 Rust tests; `cargo clippy` clean with zero warnings on three
  targets
- 143 Python tests on native Windows, plus the Windows and Linux companions
  exercised on a managed host: grouped menu, gauges, alert switch, spool path,
  and the unsupported-desktop path still refusing to draw
