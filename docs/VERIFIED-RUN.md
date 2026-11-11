# Verified run — 2026-11-11 (release 0.1.0)

This run reached a full Stage 2 FS session through the **Lobby** path, using
the original `civswitch-kit` engine and bridge.

## Environment

| Item | Value |
|---|---|
| Console | Switch 2, firmware 23.0.1 |
| Game | Civilization VII, Switch 1 physical cart 1.0.0 |
| PC | Linux, wired Ethernet 10.42.0.1 |
| Console | 10.42.0.20 |
| Node.js | 22.x |
| Python | 3.14 |
| Command | `python3 IZCIVSwitch.py --lobby --yes` |
| Run folder | `kit/port/engine/runs/switch2-nTDhp6` |
| Acquisition | attempt 2, ~669 s |
| Runtime cap | `--max-runtime 720` (the repository default is 900) |

## Key output

```
[engine] Connected. Checking the application...
[engine] 1/4 Checking the console
[run] app/qualify
[engine] 2/4 Acquiring FS memory
[run] FS layout
[run] Owned FS root
[run] Owned FS notifier
[run] ro/test-sm
[run] ro/copy-loader-root
[run] ro/prepare-workers
[run] RO payload and current console policy
[run] ro/bind-sessions
[run] ro/prepare-event
[run] ro/test-gate
[run] ro/launch
[run] Start RO payload
[run] RO instruction challenges
[run] Restore Loader session
[engine] 4/4 Running the FS demo
[run] process/bind-notifier
[run] process/qualify
[run] {"verified":true,... "trials":2,"restored":true}
[run] Remove RO donor files
[engine] 4/4 verified. Civilization VII via CivSwitch RPC and FS memory endpoint remain live ...
```

## Final state

```
verified: True
rpc: { "mode": "held", "state": "closed", "reason": "SIGINT" }
retainedEndpoint: { "ready": true, "session": "switch2-nTDhp6", "socketPath": "127.0.0.1:43251" }
cleanup: { "deferred": true, "donor": { "cleanedUp": true, "files": ["main.npdm", "main"] } }
```

All 26 pipeline stages are `complete`, including:

```
app/map
app/inspect-mounts
Remove exploit scratch from prior launches
app/qualify
FS read, write and restoration
retained/find-metadata
ro/install-retained
FS layout
Owned FS root
Owned FS notifier
ro/test-sm
ro/copy-loader-root
ro/prepare-workers
RO payload and current console policy
ro/bind-sessions
ro/prepare-event
ro/test-gate
ro/launch
Start RO payload
RO instruction challenges
Restore Loader session
process/bind-notifier
process/qualify
FS instruction challenges
Remove RO donor files
Release FS resources
```

The console bridge reported:

```
=== civ_bridge: exiting after 319496 RPC exchanges ===
Executed successfully
```

and the engine printed:

```
FS execution verified. Original instructions restored and scratch cleaned up.
Restart the console when finished.
```

## Payload identity

The Lobby injector and the engine use the same loader code. Two source files
with different formatting:

| Source | Bytes | Minified/compressed |
|---|---|---|
| `CivSwitchLDN/payloads/core.js` | 60 889 | 19 lines, SHA `0e3e46f3…` |
| `CivSwitch/core.js` | 60 691 | 19 lines, SHA `0e3e46f3…` |

Both produce byte-identical 19-line chat payloads:
`0e3e46f35002ca701179c4a4d945e9e55c0a190359d220aa66b5e5c627520d90`.

## Failure modes seen during development

- `FS acquisition did not complete` after `2/4`: probabilistic fs-race miss;
  hard power-cycle and retry.
- `Got unstable rw primitive` followed by errors `604:48` and `657:28`: the
  initial Civ7 JS exploit failed in the stable-primitive layer (`addrof`), so
  the loader never opened `:9026`. This is a boot-time XSS failure, not a
  Stage 2 engine failure.
- A wedged console shows `ready:false` on the RPC bridge and a frozen
  `acquisition.log`; hard power-cycle.
