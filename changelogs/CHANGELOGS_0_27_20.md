# CDX Manager 0.27.20

Release date: 2026-11-26

## Fixes

- Sessions now launch with `PLAYWRIGHT_SKIP_BROWSER_GC=1` by default. Projects
  share one Playwright browser cache while pinning different Playwright
  versions, and an install from one project deleted the builds another project
  still needed. An explicit value in the environment still wins.
- The `UserPromptSubmit` notification hook refuses a prompt larger than 1 MB,
  such as a pasted browser console log, and saves its text to
  `~/.cdx/oversized-prompts/` (readable only by the owner). A prompt over the
  API's 32 MB text limit stayed in the history and made every retry and
  `/compact` fail until the turn was rewound; the refusal now names the saved
  file so the next message can point the agent at it.
