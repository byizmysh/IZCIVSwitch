# CivSwitch FS Kit — IZlauncher Edition

**A PC-side launcher for the CivSwitch / ns2jb Stage 2 FS session on Nintendo Switch 2.** Inject the loader through the Civilization VII multiplayer lobby, run the original `civswitch-kit` engine and bridge, and keep the retained FS RPC endpoint alive while the process is open. Includes the optional **IZlauncher 0.27** menu with an embedded loader.

**Standalone integration.** The `civswitch-kit` engine, bridge and save tools are used as published. This repository adds the PC-side runner, the Lobby installer and the launcher package. The kit is not patched.

[Safety notice](DISCLAIMER.md) · [Release notes](RELEASE_NOTES.md)

> **Use with caution.** This is research software for hardware you own. It writes under `save:/`, races the `fs` sysmodule and can leave the console wedged. A failed attempt can require a hard power-cycle (hold power for 12 seconds). Back up anything you care about first. No warranty; you are responsible for the operations you run.

## Verified run

On 2026-11-11 this exact chain completed on hardware:

```
4/4 verified
FS execution verified. Original instructions restored and scratch cleaned up.
26/26 pipeline stages complete
retainedEndpoint: { ready: true }
319 496 RPC exchanges
```

Run folder: `kit/port/engine/runs/switch2-nTDhp6`.
See [`docs/VERIFIED-RUN.md`](docs/VERIFIED-RUN.md).

---

## Installation

> **Read this section first.** The release archive does **not** contain `prod.keys`. You must supply your own console dump for the PC-side Lobby injection.

### 1. Download and extract

| Package | Use |
|---|---|
| `civswitch-fs-kit-0.1.0-linux-x86_64.tar.gz` | Full package: kit + PC Lobby runtime + launcher; Linux x86_64 |
| `civswitch-fs-kit-0.1.0-source.zip` | Scripts + kit + launcher, no Lobby runtime; use with an existing `iz2s-panel` or the Switch 1 NRO |

Extract the **entire** archive to a writable folder. Do not run from inside the archive.

```text
civswitch-fs-kit-0.1.0/
├── run-fs.py
├── pc-install-trigger.py
├── kit/                         # original civswitch-kit
├── panel/                       # PC-side CivSwitchLDN (full archive only)
│   └── data/
│       ├── runtime/civswitchldn/
│       └── private/civswitchldn/   <-- prod.keys goes here
├── izlauncher/                  # optional menu 0.27
├── README.md
├── DISCLAIMER.md
└── RELEASE_NOTES.md
```

### 2. Provide `prod.keys`

`prod.keys` is **required only for the PC-side Lobby injection** (`run-fs.py --lobby` and `pc-install-trigger.py`). It is **not needed** for `run-fs.py --no-lobby` / XSTRIG, and it is **not included** in the release.

Place your own `prod.keys` here:

```bash
panel/data/private/civswitchldn/prod.keys
```

Recommended permissions:

```bash
chmod 700 panel/data/private/civswitchldn
chmod 600 panel/data/private/civswitchldn/prod.keys
```

The file is a standard text `prod.keys` dump from **your own console**. It must contain at least these 32-hex-character entries (the LDN panel checks them):

```
aes_kek_generation_source
aes_key_generation_source
master_key_00
master_key_12
```

`title.keys` is not required for the Lobby injector. Do not download keys from untrusted sources, and never commit them to a repository.

If you do not have `prod.keys`, skip the Lobby path and use the Switch 1 NRO from the original kit to install `XSTRIG.Civ7Save`; after that, `run-fs.py --no-lobby` needs no keys.

### 3. Restore raw-socket capabilities

The bundled Lobby runtime needs `cap_net_admin` and `cap_net_raw` on:

```text
panel/data/runtime/civswitchldn/bin/python-ldn
```

After extracting the archive, run:

```bash
sudo setcap cap_net_admin,cap_net_raw=ep \
  panel/data/runtime/civswitchldn/bin/python-ldn

getcap panel/data/runtime/civswitchldn/bin/python-ldn
```

Expected:

```
cap_net_admin,cap_net_raw=ep
```

The full archive is **Linux x86_64** and its bundled Python runtime is built for Python 3.14. On another architecture or Python version, install the upstream `iz2s-panel` Lobby runtime and point the script at it with `--panel`, or use the Switch 1 NRO.

### 4. Verify the installation

```bash
python3 -m py_compile run-fs.py pc-install-trigger.py izlauncher/install.py
python3 pc-install-trigger.py --check
```

Expected:

```
panel : .../civswitch-fs-kit-0.1.0/panel
kit   : .../civswitch-fs-kit-0.1.0/kit
radio : phyN
[ok] LDN environment is ready
```

If `--check` reports `prod.keys not ready`, re-read step 2. If it reports capabilities, re-run step 3. If the radio is missing, reconnect the USB Wi-Fi adapter.

### 5. Launch

On S2: **Civ7 → MULTIPLAYER → WIRELESS → CREATE GAME → HOST LOBBY**. Keep the lobby open.

On the PC:

```bash
cd civswitch-fs-kit-0.1.0
python3 run-fs.py --lobby --yes
```

Success:

```
4/4 verified
FS ENDPOINT IS LIVE
```

`Ctrl-C` releases the FS endpoint and lets the engine clean up.

---

## Compatibility

| Path | Platform | Requirements |
|---|---|---|
| PC Lobby injection (`run-fs.py --lobby`, `pc-install-trigger.py`) | **Linux x86_64** | bundled `panel/`, Wi-Fi radio, Node.js 20+, Python 3.10+, your own `prod.keys` |
| Engine + bridge (`run-fs.py --no-lobby`) | Windows, macOS, Linux | Node.js 20+, Python 3.10+; loader already armed |
| XSTRIG install via Switch 1 | original kit | `switch1/civswitch-ldn-nx.nro` from the upstream kit (not included here) |
| IZlauncher 0.27 menu | Civ7 1.0.0 + Switch 2 | optional; installed into `save:/` |

Console prerequisites:

| Item | Requirement |
|---|---|
| Switch 2 | firmware **23.0.1** (do not update) |
| Civ7 | Switch 1 physical cart **1.0.0** |
| PC | wired Ethernet to the console; Wi-Fi adapter for Lobby injection |

The PC Lobby injection uses the existing `CivSwitchLDN` implementation: it temporarily releases the Wi-Fi radio, joins the Civ7 lobby, sends the compressed `core.js` in 19 chat messages, and restores Wi-Fi. Ethernet stays connected.

---

## First connection

1. Start Civ7 and enter `MULTIPLAYER > WIRELESS > CREATE GAME > HOST LOBBY`. The console must stay in the lobby.
2. On the PC:

```bash
python3 run-fs.py --lobby --yes
```

3. The script injects `core.js`, waits for the loader on `:9026`, starts `node kit/port/engine/run.cjs --rpc <PC_IP>`, and sends a temporary copy of `kit/port/civ_bridge.js` with `PC_IP` set.
4. Wait for `4/4 verified` and `FS ENDPOINT IS LIVE`.
5. Keep the process open while using FS. `Ctrl-C` releases and cleans up.

### If the console IP changes

The console may get a new DHCP address (`.20` → `.190`). `run-fs.py` checks the panel state and the ARP table. The loader screen always shows the authoritative address:

```
Awaiting payload at <IP>:9026
```

Force it if needed:

```bash
python3 run-fs.py --lobby --yes --console-ip 10.42.0.190
```

### If the Wi-Fi radio changes

USB adapters re-enumerate as `phyN`. If the stored radio is gone and exactly one is available, the script selects it automatically. With several radios:

```bash
python3 run-fs.py --lobby --yes --phy phy27
```

---

## Persistent mode: XSTRIG + Load Game

This is the original kit's validated loop. It needs one install and a reboot, but no Lobby afterwards.

### Install once

With the PC Lobby runtime and `prod.keys`:

```bash
# S2 must be in Host Lobby
python3 pc-install-trigger.py --yes
```

The script injects `core.js`, waits for the loader, then runs the original
`kit/save-tools/restore_save.py kit/save-tools/trigger-recreate <IP>` and writes:

```
save:/saves/Single/XSTRIG.Civ7Save
1 195 911 bytes
sha256 c53a04e4ce432727c0e24348be240051b846595103ed06865b34c16bba810e7c
```

Other saves are not deleted. The Switch 1 NRO's `ZR` is the path that wipes single-player saves; this PC installer does not.

### Reboot and run

1. Hard power-cycle S2: hold power for 12 seconds, wait 5 seconds, boot.
2. Civ7 → `Load Game` → `XSTRIG.Civ7Save`.
3. Wait for `Awaiting payload at <IP>:9026`.
4. PC:

```bash
python3 run-fs.py --no-lobby
```

On failure: hard power-cycle, `Load Game → XSTRIG`, repeat. The kit reports roughly 30% success per boot; 3–4 boots are normal.

---

## Optional: IZlauncher 0.27 menu

`izlauncher/` installs a menu entry into `save:/saves/Single/IZ2S.Civ7Save`.
This is not required for FS and was not used in the verified run above.

```bash
python3 izlauncher/install.py --ip <S2-IP>
```

After `INSTALL DONE`:

1. Reboot S2.
2. Civ7 → `Load Game` → `IZ2S.Civ7Save` → menu.
3. Double-press **R3** (right stick) to start the embedded loader.
4. PC: `python3 run-fs.py --no-lobby`.

Rollback:

```bash
python3 izlauncher/install.py --ip <S2-IP> \
  --restore izlauncher/receipts/<uuid>/receipt.json
```

---

## Observing and stopping

While `run-fs.py` is alive:

```bash
node kit/port/engine/rpc.cjs <run-folder> status
```

The bridge is up during `2/4`, so `status` can answer before FS is fully acquired.
Inspect a run without starting a new engine:

```bash
python3 run-fs.py --inspect kit/port/engine/runs/<run-folder>
```

Monitor prefixes:

| Prefix | Meaning |
|---|---|
| `[engine]` | selected `run.cjs` lines |
| `[run]` | `run.log`: pipeline stages |
| `[fs] profile` / `[fs] retry` | fs-race sweep |
| `[fs] heartbeat` | stage, attempt, elapsed, RPC calls, idle |
| `[fs] WARNING` | no acquisition progress for 180 s |
| `RUN SUMMARY` | verified/error, stages, last retries |

`Ctrl-C` releases the endpoint. If the process does not exit, `kill <pid>`; the console may be wedged.

---

## What you can do

- Hold a live Stage 2 FS RPC endpoint on the console.
- Use the kit's RPC tooling (`rpc.cjs`, low-level `call`/`read`/`write`/`query`).
- Dump system CodeFS with `--dump-firmware` (needs ≥512 MiB free).
- Install the optional IZlauncher 0.27 menu.
- Use XSTRIG + Load Game for a persistent entry without Lobby or Switch 1.

This is not a graphical file manager. FS operations are exposed through the original kit's RPC/RO pipeline.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| `prod.keys not ready` | Put your own dump at `panel/data/private/civswitchldn/prod.keys`; required entries in step 2. |
| `capabilitiesReady: false` | Re-run the `setcap` command from step 3. |
| `radio phyN is absent` | Reconnect the USB Wi-Fi adapter; one radio → auto; several → `--phy`. |
| `loader did not answer` | S2 is not in Host Lobby, or the IP changed; pass `--console-ip`. |
| `Got unstable rw primitive` + `604:48` / `657:28` | Initial Civ7 JS exploit failed at the stable-primitive layer; no `:9026`. Hard reset and retry. |
| `FS acquisition did not complete` | Probabilistic fs-race miss; hard reset, repeat. |
| Stuck at `2/4`, `idle` grows | Wedge; hard power-cycle 12 s. |
| `rpc.cjs status` → `ECONNREFUSED` | Engine stopped or bridge busy; use `--inspect`. |
| `RUN SUMMARY verified: False` | Read the summary and `switch2/acquisition.log`. |
| Release on non-Linux / other Python | Use the source package with your `iz2s-panel`, or the Switch 1 NRO; the bundled Lobby runtime is Linux x86_64 / Python 3.14. |

The verified run took 669 s and succeeded on acquisition attempt 2. `--max-runtime`
defaults to 900 s; `--max-runtime 0` allows the kit's 3 × 10-minute retry budget.

---

## Privacy and security

- The scripts run locally and do not contact a cloud service.
- `prod.keys` is console-specific and must never be committed or shared.
- The release archive contains no keys, no `title.keys`, and no Switch 1 `.nro`.
- Writes occur under `save:/` (trigger save, scratch, optional menu capsule).
- The FS race can wedge the console; a hard power-cycle is expected.
- Use only consoles and content you are authorized to access. No Nintendo branding or game assets are included.

## Credits and license

- [civswitch-kit](https://gitee.com/mza1010/civswitch-kit) — GPL-2.0
- `kurumuz/ns2jb` → `slapah/CivSwitch` → kit patches
- Civ7 XSS / loader portions: Gezine (MIT), see `LICENSE-MIT-Gezine.txt`
- IZlauncher package: CivSwitch GPL-2.0 + IZ2S license, bundled in
  `izlauncher/package/`
- This integration: GPL-2.0, see `LICENSE`

See [`NOTICE.md`](NOTICE.md) for details.
