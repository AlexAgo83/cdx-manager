# CDX Manager 0.24.5

Release date: 2026-10-29

This patch adds isolated workspace runs with opt-in network access. (#61)

## Workspace runs

- Add `cdx run --isolate-workspace` for Linux workspace confinement through bubblewrap, exposing the checkout, permitted toolchains, shared caches, and provider authentication while keeping the operator's home and host processes outside the boundary. (#61)
- Add `--network-access` to enable Codex's workspace-write network setting while retaining its workspace sandbox. (#61)
- Preserve both options across detached runs and failover, and advertise `workspace_isolation` and `workspace_network` capabilities in `cdx schema`. (#61)

## Maintenance

- Record tray companion checksums for v0.24.4. (`7465b2e8244e90032d1ab8b7ad7af6a26ffe805c`)
- Record release archive checksums for v0.24.4. (`a0afa21ccc816769fb0aac5883912efd90bf1028`)
