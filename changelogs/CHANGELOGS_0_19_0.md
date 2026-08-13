# CDX Manager 0.19.0

## Features

- Tray alerts can return to their originating iTerm session on macOS, including from a native notification banner.
- The tray can group enabled Logics actions by repository and opens its viewer on a free local port.
- The tray offers supported terminal choices and persists its session sort order.
- Interactive launches ask for an optional agent-alert hook and support a validated manually entered launch directory.

## Fixes

- Tray session rows now show only meaningful quota reset columns and retain their selected terminal behavior across macOS, Windows, and WSL.
- Existing provider hooks read the current alert mute setting, so `cdx tray alerts on|off` takes effect without a relaunch.
- Local tray development helpers now use the checkout reliably on Windows and WSL.
