# CDX Manager 0.24.7

Release date: 2026-10-29

This patch fixes command execution in isolated Codex workspace runs. (#65)

## Workspace runs

- Drop Codex's nested sandbox when `--isolate-workspace` is enabled, avoiding the user namespace mapping failure that prevented commands from running. The outer workspace sandbox remains the isolation boundary. (#65)
- Remove Codex's sandbox mode and network overrides inside the isolated workspace and pass `--dangerously-bypass-approvals-and-sandbox`; the outer sandbox controls network access and keeps review runs read-only through its workspace mount. (#65)

## Maintenance

- Record tray companion checksums for v0.24.6. (`87aba5d2cffdfb1a96e386abcdabe54df9ee4808`)
- Record release archive checksums for v0.24.6. (`6b92094143ea28bf0cc096aef88d1015565aba18`)
