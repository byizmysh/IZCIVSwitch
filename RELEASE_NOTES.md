# Release notes — 0.1.0

Released: 2026-11-11

## Verified

Full hardware run through the Lobby path:

```
run: switch2-nTDhp6
verified: True
26/26 pipeline stages complete
retainedEndpoint.ready: True
319 496 RPC exchanges
FS execution verified. Original instructions restored and scratch cleaned up.
```

Acquisition succeeded on attempt 2 after ~669 s.

## Included

- `run-fs.py` — Lobby injection → loader → engine → bridge → held RPC,
  with live logs, stall detection, `RUN SUMMARY` and `--inspect`.
- `pc-install-trigger.py` — PC-side replacement for Switch 1 +
  `civswitch-ldn-nx.nro`; writes `XSTRIG.Civ7Save` through the original
  `kit/save-tools/restore_save.py`.
- `kit/` — original `civswitch-kit` (engine, bridge, save tools).
- `panel/` — minimal `CivSwitchLDN` + Linux x86_64 runtime for PC-side Lobby
  injection. `prod.keys` is **not** included.
- `izlauncher/` — optional IZlauncher 0.27 menu with an embedded loader
  (double-R3), install/rollback via `install.py`.

## Assets

| Asset | Notes |
|---|---|
| `civswitch-fs-kit-0.1.0-linux-x86_64.tar.gz` | Full package; Linux x86_64 + Python 3.14 Lobby runtime |
| `civswitch-fs-kit-0.1.0-source.zip` | Scripts + kit + launcher; no Lobby runtime |

## Known limitations

- PC-side Lobby injection is Linux x86_64 only with the bundled runtime.
  Other systems can use the engine with `--no-lobby` after an XSTRIG/S1 install.
- The Switch 1 installer `.nro` is not included; obtain it from the upstream
  kit if you need it.
- `prod.keys` is not included; supply your own dump.
- The FS race remains probabilistic (~30% per boot). The verified run needed
  two acquisition attempts.
- The IZlauncher 0.27 menu path was not part of the verified FS run.

## Licensing

GPL-2.0 for this integration. Upstream components retain their licenses; see
`NOTICE.md`, `LICENSE`, `LICENSE-MIT-Gezine.txt`, and the files inside
`izlauncher/package/`.
