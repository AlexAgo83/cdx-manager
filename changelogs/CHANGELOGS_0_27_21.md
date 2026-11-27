# CDX Manager 0.27.21

Release date: 2026-11-27

## Improvements

- Add `--on-busy allow` (also `--on-busy=allow`) to launch a second session
  on a busy profile without confirmation, including without a terminal or with
  `--json`. The shared-login warning goes to stderr so JSON stdout remains
  parseable. Support task, directory, prompt and resume launches; keep `ask`
  as the default and preserve `fail`. (#162, ff016fb1907ba093eca6b29c1e6b2e55db9fc401)

## Maintenance

- Record the GitHub release archive checksums for v0.27.20.
  (127e435529d10aefd566c10b6f7b783f3e5eaaa6)
