# NOTICE

This repository is an integration layer for
[civswitch-kit](https://gitee.com/mza1010/civswitch-kit). It does not claim
authorship of the Civ7 XSS, the ns2jb Stage 2 engine, or the CivSwitch loader.

## Upstream

- civswitch-kit (GPL-2.0) — <https://gitee.com/mza1010/civswitch-kit>
- slapah/CivSwitch — ns2jb-port layer
- kurumuz/ns2jb (GPL-2.0) — upstream Stage 2 research
- Gezine/CivSwitch — Civ7 XSS and loader portions (MIT), preserved in
  `LICENSE-MIT-Gezine.txt`

The `kit/` directory is the original upstream source, included for
convenience. The kit's licenses and notices remain in force.

## Not included

- `prod.keys`, `title.keys`, or any console keys;
- the Switch 1 installer `civswitch-ldn-nx.nro`;
- firmware dumps or save backups;
- the full `iz2s-panel` platform. The `panel/` directory contains only the
  `CivSwitchLDN` component, its Linux x86_64 runtime, and the panel state
  needed for PC-side Lobby injection.

The PC-side Lobby injector uses the `CivSwitchLDN` implementation from
`iz2s-panel/iz2s-platform-run22`. Its source and licenses are preserved under
`panel/`.

## Bundled launcher package

`izlauncher/package/` contains an IZlauncher 0.27 build with the CivSwitch
loader embedded:

- `LICENSE-CivSwitch.txt` (GPL-2.0 portions);
- `LICENSE-IZ2S.txt`;
- `boot.js`, `capsule-source.js`, `menu-capsule.bin`,
  `IZlauncher-027-FS.Civ7Save`, `pad-normalize.comp.spv`.

## License of this repository

GPL-2.0. See `LICENSE`.

## Safety

Research only, on hardware you own. A failed fs race or a wedged console is an
expected failure mode; hard power-cycle the console. Do not use this on other
people's devices or in online play. No warranty.
