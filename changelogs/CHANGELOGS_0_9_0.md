# CDX Manager 0.9.0

## Highlights

- Adds an observable assistant run registry for CDX sessions.
- Generates the Logics corpus for assistant-run observability so follow-up work can be tracked from requests through closeout.
- Closes the observable run registry workflow chain after validation.

## Validation

- `npm run prepublishOnly`
- `npm pack --dry-run`
- `logics-manager lint --require-status`
- `logics-manager audit --legacy-cutoff-version 1.1.0 --group-by-doc`
