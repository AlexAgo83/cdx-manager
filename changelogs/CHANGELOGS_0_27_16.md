# CDX Manager 0.27.16

Release date: 2026-11-18

## Fixes

- `cdx stats` counts a run that spans several days, or is still running, on
  the days it actually worked, read from each transcript record's own time.
  A two-day session used to be filed whole on its launch day, and a running
  one had no usage at all, so `--since today` missed its work today. Derived
  on read, never stored; one-day runs are unchanged.
- The usage readers stream transcripts up to 2 GiB and parse only the lines
  that carry usage. A long Claude session (236 MB) was over the old 128 MB
  bound and was never counted, not even when it ended.

## Display

- TOTAL leaves out cache reads, which re-read the whole context on every turn
  and were 99.9 % of a long session's figure; the totals line lists them
  beside it.
- A profile on a plan (a Claude login, or Codex signed in with ChatGPT) shows
  `plan` in USD~ instead of a list price it never pays. The list price stays
  in `--json` and in the totals line.
