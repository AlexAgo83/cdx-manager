# CDX Manager 0.27.14

Release date: 2026-11-15

## Fixes

- Read an interactive launch whose supervisor was killed (closed terminal,
  SIGKILL) as interrupted at its transcript's last write. It used to stay
  "running" with no end, so `cdx stats` and `cdx history` filed days of usage
  on the launch day and a long session that ended today was missing from
  today's figures. Derived on read, never stored (#152).

## Maintenance

- Attach the checksum ledger to each release from the npm, PyPI and checksum
  workflows (#149).
- Close the cdx-tray split corpus with its acceptance proofs (#150) and close
  req_084 and remote messaging items 168 to 170 on their recorded evidence
  (#151).
- Record release archive checksums for v0.27.13
  (15e55de).
