# IZCIVSwitch

IZCIVSwitch is a PC-side research toolkit for Nintendo Switch 2 and Civilization VII.

**PC compatibility.** The bundled Lobby runtime targets Linux x86_64.

[Release notes](https://github.com/byizmysh/IZCIVSwitch/releases/tag/v0.1.0) · [Safety notice](DISCLAIMER.md)

> **Use with caution.** This research software can modify game save data and cause the console to freeze. Back up your saves before use. A freeze may require a full power cycle. Use the software only with hardware and content you are authorized to access. It comes without a warranty.

## Installation

**Checksums.** For release archives, use the SHA-256 checksum file under **Assets** on the v0.1.0 release page. The [v0.1.0 source manifest](https://github.com/byizmysh/IZCIVSwitch/blob/v0.1.0/SHA256SUMS) covers the files in that Git tag.

> **Read this section first.** The release archive does **not** contain `prod.keys`. You must supply your own console dump for the PC-side Lobby injection.

### 1. Download and extract

| Package | Use |
|---|---|
| `IZCIVSwitch-0.1.0-linux-x86_64.tar.gz` | Full package: kit + PC Lobby runtime + launcher; Linux x86_64 |
| `IZCIVSwitch-0.1.0-source.zip` | Scripts + kit + launcher, no Lobby runtime; use with an existing `iz2s-panel` or the Switch 1 NRO |

Extract the **entire** archive to a writable folder. Do not run from inside the archive.

```text
IZCIVSwitch-0.1.0/
├── IZCIVSwitch.py
├── pc-install-trigger.py
├── kit/                         # original civswitch-kit
├── panel/                       # PC-side CivSwitchLDN (full archive only)
│   └── data/
│       ├── runtime/civswitchldn/
│       └── private/civswitchldn/   <-- prod.keys goes here
├── izlauncher/                  # optional menu
├── README.md
├── DISCLAIMER.md
└── RELEASE_NOTES.md
```

### 2. Provide `prod.keys`

`prod.keys` is **required only for the PC-side Lobby injection** (`IZCIVSwitch.py --lobby` and `pc-install-trigger.py`). It is **not needed** for `IZCIVSwitch.py --no-lobby` / XSTRIG, and it is **not included** in the release.

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

If you do not have `prod.keys`, skip the Lobby path and use the Switch 1 NRO from the original kit to install `XSTRIG.Civ7Save`; after that, `IZCIVSwitch.py --no-lobby` needs no keys.

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
python3 -m py_compile IZCIVSwitch.py pc-install-trigger.py izlauncher/install.py
python3 pc-install-trigger.py --check
```

Expected:

```
panel : .../IZCIVSwitch-0.1.0/panel
kit   : .../IZCIVSwitch-0.1.0/kit
radio : phyN
[ok] LDN environment is ready
```

If `--check` reports `prod.keys not ready`, re-read step 2. If it reports capabilities, re-run step 3. If the radio is missing, reconnect the USB Wi-Fi adapter.

### 5. Launch

On S2: **Civ7 → MULTIPLAYER → WIRELESS → CREATE GAME → HOST LOBBY**. Keep the lobby open.

On the PC:

```bash
cd IZCIVSwitch-0.1.0
python3 IZCIVSwitch.py --lobby --yes
```

Success:

```
4/4 verified
FS ENDPOINT IS LIVE
```

`Ctrl-C` releases the FS endpoint and lets the engine clean up.

---

## Compatibility

**Linux only.** PC Lobby mode runs only on Linux. The bundled runtime targets x86_64.

Console prerequisites:

| Item | Requirement |
|---|---|
| Switch 2 | firmware **23.0.1** (do not update) |
| Civ7 | Switch 1 physical cart **1.0.0** |
| PC | wired Ethernet to the console; Wi-Fi adapter for Lobby injection |

The PC Lobby injection uses the existing `CivSwitchLDN` implementation: it temporarily releases the Wi-Fi radio, joins the Civ7 lobby, sends the compressed `core.js` in 19 chat messages, and restores Wi-Fi. Ethernet stays connected.

---

## First connection

### If the console IP changes

The console may get a new DHCP address (`.20` → `.190`). `IZCIVSwitch.py` checks the panel state and the ARP table. The loader screen always shows the authoritative address:

```
Awaiting payload at <IP>:9026
```

Force it if needed:

```bash
python3 IZCIVSwitch.py --lobby --yes --console-ip 10.42.0.190
```

### If the Wi-Fi radio changes

USB adapters re-enumerate as `phyN`. If the stored radio is gone and exactly one is available, the script selects it automatically. With several radios:

```bash
python3 IZCIVSwitch.py --lobby --yes --phy phy27
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
python3 IZCIVSwitch.py --no-lobby
```

On failure: hard power-cycle, `Load Game → XSTRIG`, repeat. The kit reports roughly 30% success per boot; 3–4 boots are normal.

---

## Optional: IZlauncher menu

`izlauncher/` installs a menu entry into `save:/saves/Single/IZ2S.Civ7Save`.
The main FS session works without this optional menu.

```bash
python3 izlauncher/install.py --ip <S2-IP>
```

After `INSTALL DONE`:

1. Reboot S2.
2. Civ7 → `Load Game` → `IZ2S.Civ7Save` → menu.
3. Double-press **R3** (right stick) to start the embedded loader.
4. PC: `python3 IZCIVSwitch.py --no-lobby`.

Rollback:

```bash
python3 izlauncher/install.py --ip <S2-IP> \
  --restore izlauncher/receipts/<uuid>/receipt.json
```

---

## Observing and stopping

While `IZCIVSwitch.py` is alive:

```bash
node kit/port/engine/rpc.cjs <run-folder> status
```

The bridge is up during `2/4`, so `status` can answer before FS is fully acquired.
Inspect a run without starting a new engine:

```bash
python3 IZCIVSwitch.py --inspect kit/port/engine/runs/<run-folder>
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
- Install the optional IZlauncher menu.
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
| Stuck at `2/4`, `idle` grows | Wedge; hard power-cycle 12 s. |
| `rpc.cjs status` → `ECONNREFUSED` | Engine stopped or bridge busy; use `--inspect`. |
| `RUN SUMMARY verified: False` | Read the summary and `switch2/acquisition.log`. |
| PC platform and bundled Python | PC Lobby mode requires Linux. The bundled runtime targets Linux x86_64 and uses Python 3.14. |

---

## Privacy and security

- The scripts run locally and do not contact a cloud service.
- Keep console-specific keys private. Never commit or share them. The release archives exclude console keys and the Switch 1 NRO.
- The toolkit can write to game saves and create temporary data under `save:/`. See the [safety notice](DISCLAIMER.md) for the risks of running it.
- The release includes no Nintendo branding or game assets.

## Credits and license

- **civswitch-kit by mza1010.** [civswitch-kit](https://gitee.com/mza1010/civswitch-kit) provides the filesystem support used by IZCIVSwitch. The bundled kit retains its [GPL-2.0 license](kit/LICENSE) and [upstream notices](kit/NOTICE.md), which credit [kurumuz/ns2jb](https://gitlab.com/kurumuz/ns2jb) and the CivSwitch port by [slapah](https://github.com/slapah).
- **CivSwitchLDN by ItsNerisma.** The PC Lobby mode uses [CivSwitchLDN](https://github.com/ItsNerisma/CivSwitchLDN) by ItsNerisma. The bundled application and ItsNerisma's original code are licensed under [GPL-3.0-only](panel/engines/CivSwitchLDN/LICENSE). Reused components retain the licenses documented in the [bundled third-party notices](panel/engines/CivSwitchLDN/THIRD_PARTY_NOTICES.md).
- **IZCIVSwitch.** The original integration code is licensed under [GPL-2.0](LICENSE). Bundled projects retain their own licenses. [IZCIVSwitch repository](https://github.com/byizmysh/IZCIVSwitch)
- **Gezine's CivSwitch.** The Civilization VII XSS and loader portions retain their [MIT license notice](LICENSE-MIT-Gezine.txt). [Gezine/CivSwitch repository](https://github.com/Gezine/CivSwitch)
- **IZlauncher.** The bundled launcher comes from [IZ2S Platform](https://github.com/byizmysh/IZ2S-Platform). The package includes the [IZ2S GPL-2.0 license](izlauncher/package/LICENSE-IZ2S.txt) and [Gezine's MIT notice](izlauncher/package/LICENSE-CivSwitch.txt).
- **Related project.** [CivHomebrew](https://github.com/XITRIX/CivHomebrew) by XITRIX.

See [NOTICE.md](NOTICE.md) for detailed attribution.
