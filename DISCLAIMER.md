# Safety notice

This is research software for a Nintendo Switch 2 that you own. It exercises a
known Civ7 JavaScript-XSS chain and the ns2jb Stage 2 FS race. Read this before
running anything.

## What it writes

- `save:/saves/Single/XSTRIG.Civ7Save` (optional trigger install)
- `save:/IZ2SOffline/<uuid>/` (installer backup/staging)
- `save:/IZ2S/...` (optional IZlauncher menu and its capsule)
- `save:/NS2_GAP_*` and related scratch during the FS race

The engine attempts to restore instructions and remove scratch. It does not
provide transactional backups. A crash or power loss can leave the console in
an unknown state.

## Failure modes

- The FS race is probabilistic. A failed attempt can wedge the console.
- A wedged console requires a hard power-cycle: hold power for 12 seconds.
- The initial Civ7 JS exploit can fail before the loader opens `:9026`
  (`Got unstable rw primitive`, errors `604:48` / `657:28`).
- An uncertain native operation must not be replayed. Restart the console
  before trying again.
- Do not run two engines or two Lobby injectors at once.

## Keys

`prod.keys` is a console-specific secret. The release archive does **not**
contain it. Put your own dump at:

```
panel/data/private/civswitchldn/prod.keys
```

Never commit it, publish it, or share a live run folder. Never download keys
from untrusted sources.

## Scope

Use only hardware and content you are authorized to access. Do not use this on
other people's devices or in online play. No Nintendo branding or game assets
are included. The software is provided without warranty; you are responsible
for the operations you choose.
