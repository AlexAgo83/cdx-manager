# CDX Manager 0.21.3

## Fixes

- Claude in Chrome now works from CDX Claude profiles (`claude --chrome`, `/chrome`, or `cdx set <name> --extra-args '--chrome'`). Profile isolation redirects HOME, so Claude Code looked for Chrome and its Claude extension inside the profile home, found neither, and never installed its native-messaging host where Chrome reads it. CDX now links the real Chrome directory into each Claude profile home, as it already did for the macOS keychain: `~/Library/Application Support/Google/Chrome` on macOS, `~/.config/google-chrome` on Linux. Windows needed no change: Chrome lives under `%LOCALAPPDATA%` and the host is registered in the registry, neither of which CDX redirects. Profile copies keep the link as a link and never copy the Chrome profile itself.
