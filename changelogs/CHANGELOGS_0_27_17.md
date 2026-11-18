# CDX Manager 0.27.17

Release date: 2026-11-18

## Features

- `cdx stats --by day` gives one row per local day, oldest first. A run that
  spanned several days counts on each day it worked, from its transcript
  records' own times; its duration stays on its first day. Jarvis HQ draws its
  token chart from it.
