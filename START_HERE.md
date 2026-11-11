# START HERE

Everything is in this folder. Installation is four steps.

## 1. Extract

Extract the whole archive to a writable folder. Do not run from inside the archive.

## 2. Put your `prod.keys` in the right folder

The archive does **not** include keys. The PC Lobby injector needs your own
console dump at exactly:

```
panel/data/private/civswitchldn/prod.keys
```

```bash
chmod 700 panel/data/private/civswitchldn
chmod 600 panel/data/private/civswitchldn/prod.keys
```

The file must be a text `prod.keys` dump and contain at least
`aes_kek_generation_source`, `aes_key_generation_source`, `master_key_00`,
`master_key_12` (each 32 hex characters).

If you do not have `prod.keys`, skip the Lobby path: use the Switch 1 NRO from
the original kit to install `XSTRIG.Civ7Save`, then use `run-fs.py --no-lobby`.

## 3. Restore capabilities

```bash
sudo setcap cap_net_admin,cap_net_raw=ep \
  panel/data/runtime/civswitchldn/bin/python-ldn
getcap panel/data/runtime/civswitchldn/bin/python-ldn
```

Expected: `cap_net_admin,cap_net_raw=ep`.

## 4. Verify and launch

```bash
python3 pc-install-trigger.py --check
```

Expected: `[ok] LDN environment is ready`.

On S2: Civ7 → `MULTIPLAYER > WIRELESS > CREATE GAME > HOST LOBBY`.

On the PC:

```bash
python3 run-fs.py --lobby --yes
```

Success: `4/4 verified` and `FS ENDPOINT IS LIVE`.

Read `README.md` for the persistent XSTRIG mode, the optional IZlauncher menu,
monitoring, troubleshooting and safety notes.
