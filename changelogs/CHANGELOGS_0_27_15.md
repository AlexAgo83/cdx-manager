# CDX Manager 0.27.15

Release date: 2026-11-18

## Features

- Claude conversation pages list the images a session sent to its user: a
  `SendUserFile` tool entry carries `files`, the absolute image paths it named
  (png, jpg, webp, gif; at most eight). Readers such as Jarvis HQ show those
  images in place of the bare tool line. The files themselves are never read,
  and no other entry gains a field.
