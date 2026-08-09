# CDX Manager 0.16.0

> cdx now tells you when one of its sessions finishes or needs you, which is
> the one thing it could not do in the situation it was built for: several
> assistants running in parallel across different repositories. Getting there
> meant retiring the old `cdx notify` and reserving the name for this.

## Breaking

### `cdx notify` means something else

`cdx notify <name> --at-reset` and `cdx notify --next-ready` are gone. Those
answered "when does my quota come back", which `cdx status` already answers,
and in practice the only form anyone typed was `cdx ready`.

`cdx ready` is unchanged — same behaviour, same output, same flags. If you
scripted the retired flags, `cdx ready --json` is the replacement; there is no
equivalent for waiting on one named session's reset.

`cdx notify` is now the target a provider hook calls. You do not run it
yourself.

## Features

### Notifications when a session finishes or waits for you

```text
✓ work1     logics-manager · waiting for you
✓ codex-a   cdx-manager · finished
```

The notification names the session and the repository, because the case this
exists for is several of them at once — a notification that cannot tell you
which one is not worth raising. Only cdx knows the session name, which is why
this lives here rather than in a hook you write by hand.

Nothing to set up. cdx already owns each session's home directory, so it
installs the hooks there on the next launch and says so once. Existing
sessions pick them up with no migration.

On by default. `cdx set <name> --notify off` turns it off for one session,
`cdx set --all --notify off` everywhere, and cdx removes what it installed at
that session's next launch — leaving any hooks you wrote yourself alone.

### Delivery on every platform, and silence where there is none

macOS uses `osascript`, Linux `notify-send`, native Windows a toast, and WSL
reaches the Windows notification centre through interop rather than being
treated as plain Linux — which is what it was before, and why it delivered
nothing at all there.

On a host with no way to show a notification — a headless or SSH Linux
session, or WSL with interop disabled — cdx installs no hooks. Approving a
hook that could never show you anything is a cost with no return. A host that
gains a channel later is provisioned on its next launch.

Headless `cdx run` never notifies, so a script issuing fifty runs stays quiet.
Its caller already learns of completion from the return value.

## Fixes

### The Windows notification no longer blocks

Windows notifications were a `MessageBox` spawned with no timeout. As an
occasional quota alert that was survivable. As a hook firing on every agent
turn it would have held the turn open until someone dismissed the dialog, and
a window stealing focus every turn is worse than no notification at all. It is
now a toast, which needs no dismissing.

Both providers refuse to run a hook they have not been told to trust, so the
first launch asks you to approve it once. cdx does not write that trust for
you and passes no bypass flag: the guard is there on purpose.
