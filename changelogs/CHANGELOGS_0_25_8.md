# CDX Manager 0.25.8

Release date: 2026-11-02

This patch release restores Git history and RTK access in isolated workspaces.

## Fixes

- Restore read-only Git history access in isolated local and remote workspaces, including linked worktrees with packed objects and refs. Keep Git metadata read-only and exclude host configuration, hooks, remotes, and credentials. (#91)
- Expose the installed RTK binary in isolated launches and persist its savings history in a dedicated shared cache, separate from the operator's normal RTK history. (#91)

## Maintenance

- Record tray companion checksums for v0.25.7. (`31b7ecfb8f8189f29b01aaa88f9acf866acccd19`)
- Record release archive checksums for v0.25.7. (`03d339b9e93e2d7d917df6e614132390ce4436fe`)
