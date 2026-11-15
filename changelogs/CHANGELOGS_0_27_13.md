# CDX Manager 0.27.13

Release date: 2026-11-14

## Features

- Add `cdx mcp serve`, a stdio MCP server exposing read and run tools (#147).
- Add `cdx tray stop` using the existing companion stop protocol (#146, M-1073).
- Install the tray from the separate `cdx-tray` repository and remove its source
  and build tooling from this repository. Select a compatible companion release
  by snapshot schema major version and verify it against the tray checksum
  ledger; report when no compatible release is available (34b0c4c59e6e2d9b5737fb57fa5f78acb77a832d).

## Maintenance

- Plan the `cdx-tray` split and pin the tray snapshot JSON shape per schema
  version (f5c60861bf99b310dff531da297d6e6f092a69ff).
- Restore the README's shared short structure and move detailed guidance to
  `docs/` (711876cdfad199f3262d2583e7a21e72f0ee1c28).
- Make the loop test wait for the channel inbox line rather than just the
  inbox file (cbdc399c918d263f0e2579f4f24409e80b7562c9).
- Record tray companion checksums for v0.27.12
  (d2ef1009f8430b3b4fac217847b2c305637b693f).
- Record release archive checksums for v0.27.12
  (eb025a0333fa5e781ae435c990a12a5c62bcc061).
