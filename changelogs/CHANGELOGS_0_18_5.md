# CDX Manager 0.18.5

## Fixes

### An npm install knew which version it was

`cdx --version` reported `0.0.0` for every install done through npm, and the
update banner never went away: nothing is newer than a release that believes it
is version zero, so `cdx update` ran, succeeded, and changed nothing that could
be seen.

The version is resolved from the `VERSION` file, then from Python distribution
metadata. An npm install has neither — the file was not in the published package
and npm creates no Python metadata — so both lookups missed. `VERSION` ships
now, and `package.json` becomes the last resort below it, because an npm tarball
carries that file by construction and cannot lose it the way a file list can.

Installs through `install.sh` were never affected: they unpack the git archive,
which always contained `VERSION`.

### The tray badge cleared when you read it

The count beside the icon could be raised and never lowered. `tray-icon`'s macOS
`set_title` ignores a `None` — it sets a title when given one and does nothing
otherwise — so every attempt to clear the marker was silently dropped. This
predates the unread work: the 45-second expiry it replaced cleared the same way,
so it never cleared either. Nobody noticed, because a marker that outstays its
welcome looks exactly like one that is still true.

### The tray says which CDX it actually reached

A WSL user could see `cdx --version` report the current release in their
terminal while the companion insisted CDX was too old to have `cdx tray`. Both
were right: the companion runs `wsl.exe -- cdx`, which is not a login shell, so
it resolves the system PATH and can find an older CDX that the user's own shell
never sees. The message names the command that answered now, and points at
`CDX_TRAY_CDX`, which is the setting that fixes it.

### The gauge is legible on Windows and Linux

The empty part of the capacity bar was a dither pattern, which on a dark Windows
menu reads as corrupted text rather than as an empty gauge. It is a thin rule
now, in the same Unicode block as the filled part so the column still aligns in
the proportional font a native menu uses.

## Features

### The tray menu is ordered by remaining capacity, and by nothing else

Sessions were grouped under a provider heading, which reordered the list it was
meant to organise: a group took the rank of its most constrained session, so a
healthy account could sit above the one that made the icon turn. The headings
are gone and each row names its provider.

That also removed an older defect underneath. A click carried a position into
the snapshot, which only worked while the order was stable — and ordering by
capacity makes it change under you. A row now carries the session's name, so a
poll landing between the draw and the click can no longer open the wrong one.

### Both limit windows are visible at once

Both providers meter a five-hour window and a weekly one, and the tray showed
whichever was worse. A week almost spent was invisible behind a five-hour window
that had just reset, and the figure silently changed meaning between two polls.

Each window now has its own line, its own bar and its own name. On macOS the row
also says how old its figure is and when the limit resets — the two facts you
need before trusting a percentage, which the text rows had all along and the
drawn one had never been given.

### Every session row opens into its own actions

A row that launched on click had space for exactly one meaning. Each is a
submenu now: **Open session**, which is the launch it always did, and **Launch
settings (next launch)**, a view of `cdx config <name>`. The wording is the
promise — CDX stores those settings for the next start, and no provider accepts
them for an assistant already running, so the tray never implies otherwise.

### Agent alerts say what happened, and open the session that sent them

Both providers are now subscribed to the same two hooks, `Stop` and
`PermissionRequest`, so a permission request is reported immediately and by
tool name rather than through a delayed generic notification. The duplicate that
combination used to produce is filtered where the duplication is.

Alerts reach the tray as fields rather than as a sentence, so the menu can name
the session, the project and the tool — and clicking one opens the session it
came from. The tool's arguments, the transcript path and provider session
identifiers are never part of that.

A turn that dies on a provider error also raises an alert now, where it used to
be silent: a rate limit, an overload, an authentication or billing problem. They
are marked apart from completions and say whether the failure usually clears on
its own or needs you. Claude publishes this; Codex documents no equivalent, so a
Codex turn killed by its provider stays silent.

### The alert badge and the alert list are the same thing

The marker beside the icon expired on a timer while the menu kept a list that
never cleared, so the two could not agree and neither meant anything precise.
There is one unread list now: the badge counts it, the menu shows it, and
opening the menu is what marks it read. An alert that arrives while the menu is
open stays unread, because nobody has seen it.

### `cdx update` replaces a running companion

It used to move the files and tell you to quit the tray from its menu and start
it again. It now asks the running companion to stop, replaces it, and starts the
replacement — verifying that it actually came up rather than trusting that it
was launched. If the replacement will not start, the companion that was working
is put back and restarted.

A companion that does not stop within ten seconds is left alone and reported,
never killed: an open menu blocks it on Windows, and a tray you are reading is
not a process to terminate over a version number.

### Installing the tray asks about alerts, and means it for later sessions

`cdx tray install` asks two separate questions — start at login, and notify you
when an agent finishes or waits for you. Each has its own flags, an explicit
flag never triggers a prompt, and a piped or `--json` run declines rather than
deciding for you. Accepting alerts turns them on for every supported session and
for sessions created afterwards; on Codex, the approval it will ask for at the
next launch is stated at install time.

### A Logics card in the tray, off unless you ask

`cdx tray plugin enable logics` adds one section to the menu: how much is
blocked and in progress, the first blocked document, and the highest-priority
task in progress. Clicking a row opens the Logics viewer focused on it.

There is deliberately no marketplace, no discovery and no plugin auto-update. An
adapter is a function in this repository, named in a registry CDX owns, so
nothing unknown can run. It produces data and never behaviour: a card is a
summary, rows, and action ids from a fixed vocabulary. The card is built from
`logics-manager status --format json` and nothing else, refreshed at most once a
minute, and simply absent when Logics is unavailable.

### Choose the terminal a session row opens

`cdx tray terminal set iTerm` — or Ghostty, WezTerm, kitty, `wt`. What is stored
is an application name, never a command: anything that could be read as one is
refused rather than sanitized, and the rule is applied when the value is read as
well as when it is written. macOS opens it with `open -a`, Linux prefers it
ahead of the emulators it already tries, and Windows honours `wt`, which is the
one that documents how to be handed a command. A terminal that is not installed
falls back to the platform default rather than leaving the click doing nothing.
