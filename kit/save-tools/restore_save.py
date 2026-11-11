"""Restore a save-tree backup produced by dump_save_tree.py.

Uploads each backed-up file to the console over the Remote JS Loader (:9026)
in <=400,000-char base64 chunks, then writes the files back with the fs save
primitives (CreateFile / OpenFile / SetFileSize / WriteFile / CloseFile) and
commits the "save" data.

Usage:
  python restore_save.py <backup_dir> [console_ip] [port] [--only SUBSTR]
  python restore_save.py <backup_dir> --dry-run

<backup_dir> must contain manifest.json as written by dump_save_tree.py
(e.g. save-tools/backups/2026-11-09_142719+0800).
"""
from __future__ import annotations

import base64
import json
import socket
import sys
import time
from pathlib import Path

CHUNK = 400000
TIMEOUT = 1800


def send(host: str, port: int, code: str, timeout: int = TIMEOUT) -> str:
    with socket.create_connection((host, port), timeout=8) as sock:
        sock.sendall(code.encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)
        sock.settimeout(timeout)
        data = b""
        try:
            while True:
                block = sock.recv(65536)
                if not block:
                    break
                data += block
        except socket.timeout:
            pass
    return data.decode("utf-8", "replace")


APPLY_TEMPLATE = r"""
(async function() {
try {
const F_CreateFile  = sdk_base + 0xa6700n;
const F_OpenFile    = sdk_base + 0xa78a0n;
const F_CloseFile   = sdk_base + 0xa5a70n;
const F_WriteFile   = sdk_base + 0xa5e00n;
const F_SetFileSize = sdk_base + 0xa6020n;
const F_Commit      = sdk_base + 0xa7de0n;
const F_DeleteFile  = sdk_base + 0xa6710n;
const F_CreateDir   = sdk_base + 0xa6890n;

const FILES = __FILES__;
const store = window.__restore || {};
const h = malloc(8);
const wo = malloc(8); write32(wo, 1n);
const pb = malloc(4096);

function pathBuf(p) {
    const bytes = text_encode(p);
    if (bytes.length >= 4000) throw new Error("path too long");
    for (let i = 0; i < bytes.length; i++) write8(pb + BigInt(i), BigInt(bytes[i]));
    write8(pb + BigInt(bytes.length), 0n);
}
function b64dec(s) {
    const A = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    const m = {};
    for (let i = 0; i < 64; i++) m[A[i]] = i;
    const out = [];
    let i = 0;
    while (i + 3 < s.length) {
        const c0 = m[s[i]], c1 = m[s[i + 1]];
        const p2 = s[i + 2] === "=", p3 = s[i + 3] === "=";
        const c2 = p2 ? 0 : m[s[i + 2]];
        const c3 = p3 ? 0 : m[s[i + 3]];
        const v = (c0 << 18) | (c1 << 12) | (c2 << 6) | c3;
        out.push((v >> 16) & 255);
        if (!p2) out.push((v >> 8) & 255);
        if (!p2 && !p3) out.push(v & 255);
        i += 4;
    }
    return out;
}

// Per-file errors are logged and skipped instead of aborting: a file held by
// the running game (HallofFame.sqlite -> create 0x402 / open 0xe02) must not
// prevent the final Commit. Without Commit the hard power-cycle used after
// P4 wedge discards every rewritten file (observed RUN 12: 0/30 canary).
let written = 0, skipped = 0;
for (let index = 0; index < FILES.length; index++) {
    const file = FILES[index];
    const joined = (store[file.path] || []).join("");
    const bytes = b64dec(joined);
    if (bytes.length !== file.size) {
        await log("SKIP size mismatch " + file.path + " got " + bytes.length + " expected " + file.size);
        skipped++;
        continue;
    }
    const slash = file.path.lastIndexOf("/");
    const parent = file.path.slice(0, slash);
    if (parent && parent !== "save:/saves") {
        pathBuf(parent);
        call_rop(F_CreateDir, pb);
    }
    pathBuf(file.path);
    call_rop(F_DeleteFile, pb);
    pathBuf(file.path);
    let createResult = call_rop(F_CreateFile, pb, BigInt(file.size));
    if (createResult !== 0n && BigInt.asUintN(32, createResult) !== 0x402n) {
        await log("SKIP create " + file.path + " " + toHex(createResult));
        skipped++;
        continue;
    }
    pathBuf(file.path);
    const openResult = call_rop(F_OpenFile, h, pb, 6n);
    if (openResult !== 0n) {
        await log("SKIP open " + file.path + " create=" + toHex(createResult) + " open=" + toHex(openResult));
        skipped++;
        continue;
    }
    const handle = read64(h);
    call_rop(F_SetFileSize, handle, BigInt(file.size));
    const data = malloc(file.size + 8);
    for (let i = 0; i < bytes.length; i++) write8(data + BigInt(i), BigInt(bytes[i]));
    const writeResult = call_rop(F_WriteFile, handle, 0n, data, BigInt(file.size), wo);
    call_rop(F_CloseFile, handle);
    free(data);
    if (writeResult !== 0n) {
        await log("SKIP write " + file.path + " " + toHex(writeResult));
        skipped++;
        continue;
    }
    written++;
    await log("WROTE " + file.path + " " + file.size);
}

pathBuf("save");
const commitResult = call_rop(F_Commit, pb);
if (commitResult !== 0n) { await log("E: commit " + toHex(commitResult)); return; }
await log("RESTORE DONE " + written + " written " + skipped + " skipped");
} catch (e) {
await log("EXCEPTION: " + e.message);
await log(e.stack);
}
})();
"""


def main() -> int:
    args = [a for a in sys.argv[1:]]
    if not args:
        print(__doc__)
        return 1
    backup_dir = Path(args[0])
    dry_run = "--dry-run" in args
    only = None
    if "--only" in args:
        index = args.index("--only")
        only = args[index + 1]
    positional = [a for a in args[1:] if not a.startswith("--") and a != only]
    host = positional[0] if positional else ""
    port = int(positional[1]) if len(positional) > 1 else 9026

    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    files = [f for f in manifest["files"] if only is None or only in f["path"]]
    if not files:
        print("no files selected")
        return 1
    plan = [(f["path"], backup_dir / f["stored_as"], f["bytes"], f["sha256"]) for f in files]
    total = sum(p[2] for p in plan)
    for path, local, size, digest in plan:
        print(f"{path}  {size:,} bytes  {digest}  <- {local.name if local.exists() else 'MISSING'}")
    print(f"total {total:,} bytes in {len(plan)} file(s)")
    if dry_run:
        print("dry run: nothing sent")
        return 0

    if not host:
        print("console IP required (or pass --dry-run)", file=sys.stderr)
        return 1

    send(host, port, "log('STARTING RESTORE');window.__restore=null;'reset'")
    t0 = time.time()
    for path, local, size, digest in plan:
        raw = local.read_bytes()
        if len(raw) != size:
            print(f"local size mismatch for {path}")
            return 2
        b64 = base64.b64encode(raw).decode("ascii")
        chunks = [b64[i : i + CHUNK] for i in range(0, len(b64), CHUNK)]
        key = json.dumps(path)
        for index, part in enumerate(chunks, 1):
            code = ("(window.__restore=window.__restore||{});"
                    f"(window.__restore[{key}]=window.__restore[{key}]||[]).push('{part}');"
                    f"'chunk {index}/{len(chunks)}'")
            out = send(host, port, code)
            if "Executed successfully" not in out:
                print(f"upload failed {path} chunk {index}: {out.strip()[:300]}")
                return 3
        print(f"uploaded {path} ({len(chunks)} chunk(s), {size:,} bytes)")

    meta = [{"path": p[0], "size": p[2]} for p in plan]
    apply_code = APPLY_TEMPLATE.replace("__FILES__", json.dumps(meta))
    out = send(host, port, apply_code)
    print(out)
    print(f"elapsed {time.time() - t0:.1f}s")
    return 0 if "RESTORE DONE" in out else 4


if __name__ == "__main__":
    sys.exit(main())
