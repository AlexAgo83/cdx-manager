# CDX Manager 0.27.18

Release date: 2026-11-18

## Features

- The cdx Claude status line records how full the session's context is, from
  the `context_window` Claude Code passes on each refresh, in the profile
  home (`.cdx-context.json`, figures only). A Claude conversation page
  carries it as `context.used_pct` while it is under 30 minutes old, so Jarvis
  HQ shows a context gauge beside the quota.
