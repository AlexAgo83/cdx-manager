# CDX Manager 0.24.6

Release date: 2026-10-29

This patch gives isolated online workspace runs their own egress-only network. (#63)

## Workspace runs

- Use a dedicated pasta network namespace for online `--isolate-workspace` runs, including provider transport, with port relays and host gateway mapping disabled. (#63)
- Apply nftables output filtering to reject loopback, private, link-local, and tailnet destination ranges, and use public DNS resolvers. (#63)
- Fail closed when pasta (passt), nftables, or Python 3 is unavailable, without falling back to the host network. (#63)

## Maintenance

- Record tray companion checksums for v0.24.5. (`78ba34dd71a19ac392feda771737705a72c765e5`)
- Record release archive checksums for v0.24.5. (`f835adb7acc495133438c6e719fa452843109d58`)
