# CDX Manager 0.18.3

## Fixes

### Agent alerts reach the tray companion

A running companion never received an agent alert. Notifications still arrived,
delivered the old way, and nothing reported an error — which is why it took
watching a real machine to notice.

`CDX_HOME` defaults to `~/.cdx`, resolved against `HOME`, and a provider session
runs with `HOME` redirected into its own profile because that is how cdx isolates
authentication. So a hook calling `cdx notify` resolved a different store from
the one the companion writes its heartbeat into: no heartbeat there, no tray,
deliver it directly. Both stores existed side by side on disk.

The launch environment now pins `CDX_HOME` explicitly, so a hook talks to the
same store whatever `HOME` it runs under. This takes effect for sessions started
after the upgrade; a session already open keeps the environment it was launched
with.

### The macOS menu bar icon stays visible

The icon started white and turned black about thirty seconds later, which on a
dark menu bar means invisible. `tray-icon`'s macOS `set_icon` clears the template
flag unconditionally, so every poll dropped the setting that lets macOS invert
the glyph for the current theme. It is now re-asserted after each update.

Not a bug, and worth separating: while the menu is open macOS highlights the
status item and inverts a template image, so the icon is meant to look dark
there.

## Features

### A switch to silence agent alerts

The tray menu carries a checkmark item, and `cdx tray alerts on|off|status` does
the same from a terminal.

Muting stops the banner, not the record: events keep reaching a running
companion, so the menu shows what you missed. It applies to the direct
notification path too, so quitting the tray does not silently un-mute you. It is
separate from the per-session `--notify` opt-in, which says which sessions may
alert at all.

### A readable tray menu

Session rows are selectable rather than informational — macOS renders disabled
items grey, so a dozen of them arrived as a wall of grey text. Clicking one opens
a terminal on that session.

The list is sorted by urgency, most constrained first. It previously arrived in
storage order, so an account at 1% could sit tenth while the closed icon showed
critical: the menu buried the very thing that made you open it.

## Validation

- `npm run lint`
- `npm test` — 782 Python tests
- `cargo test` — 45 Rust tests; `cargo clippy` clean with zero warnings on three
  targets
- The tray menu, its switch and the notification routing exercised against real
  sessions on macOS
