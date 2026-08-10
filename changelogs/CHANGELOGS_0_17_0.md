# CDX Manager 0.17.0

> A terminal running four cdx sessions gave you four windows titled by whatever
> each provider felt like calling itself. The title now says which session it
> is and which repository it is in, and it says it the same way for Claude,
> Codex and Antigravity.

## Features

### Interactive sessions title the terminal `session — folder`

```text
work — cdx-manager
perso — logics-manager
```

Every interactive `cdx <name>` and `cdx resume <name>` sets the window title to
its session name and the basename of the launch directory. Both halves matter:
the session is the account you are spending, the folder is the work. Neither
alone tells you which window you are looking at when several are open.

The convention comes from cdx's own launch runtime rather than from provider
flags, which is why it is identical across Claude, Codex and Antigravity. No
provider argument changed, and no undocumented option is relied on — Codex and
Antigravity do not expose one, and depending on a private flag would make this
break on their next release.

A title written once at launch does not survive: a provider TUI sets its own
whenever it repaints. cdx keeps re-asserting it for as long as the session
runs, and releases it when the session ends — on the error and interrupt paths
as well as the normal one.

Nothing is emitted where there is no terminal to emit to. `--json` launches,
redirected or piped output, `cdx run` and other headless runs, and login flows
all stay byte-for-byte as they were; a title sequence in the middle of a JSON
document its caller has to parse is a bug, not a feature. Ollama is left alone
as a local model runner rather than a cdx-managed coding session.

Session names and directories are your data, so both are stripped of escape
and control characters before the title is written. A directory named with a
raw `ESC` would otherwise end the title string early and leave the rest of the
name to be read by the terminal as commands.

cdx does not restore the previous title when a session ends. Terminals do not
reliably report the title they had, so restoring it means guessing, and
guessing wrong is worse than leaving the last true statement in place.

## Validation

- `ruff check .`
- `python3 -m pytest` — 679 tests.
- Verified against a real pty rather than a mocked stream: the launch emits
  `\x1b]0;work — cdx-manager\x07`.
- The non-TTY, `--json`, login and Ollama paths are each pinned by a test that
  asserts nothing at all is written.

## Known limits

- The em dash is written as UTF-8. A terminal whose stdout encoding cannot
  represent it — `LC_ALL=C`, for instance — gets no title rather than a
  mangled one or a crash, since every title write is best-effort.
- The refresh interval is fixed at five seconds and is not configurable. A
  provider that repaints its title more aggressively than that would show its
  own for up to that long before cdx takes it back.
