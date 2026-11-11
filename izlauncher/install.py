#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Install the working IZlauncher 0.22 (Civ7) trigger into a civswitch-kit flow.

This is the kit-native replacement for the old Node installer
``output/izlauncher-civ7-022-stable-20261111/install.cjs``.  It keeps the same
artifacts (trigger save + immutable menu capsule) but talks to the console the
same way ``civswitch-kit/save-tools/restore_save.py`` does: plain scripts over
the CivSwitch Remote JS Loader on TCP :9026, using the fs save primitives
documented in ``kit/docs/SAVE-BACKUP.md``.

What it does (install):
  1. validates the local trigger save and menu capsule against manifest.json;
  2. uploads the immutable menu capsule to save:/IZ2S/launcher022/menu-<hash>.bin
     (staged -> full SHA-256 on console -> copy to final path -> Commit);
  3. backs up the previous trigger to save:/IZ2SOffline/<uuid>/previous.bin;
  4. uploads the trigger save to save:/saves/Single/IZ2S.Civ7Save
     (staged -> full SHA-256 on console -> copy to final path -> Commit);
  5. writes receipts/<uuid>/receipt.json.

Restoring is explicit:
  python install.py --ip <S2-IP> --restore receipts/<uuid>/receipt.json

The loader must already be armed (Civ7 -> Load Game -> XSTRIG -> Awaiting
payload).  No PC transport is needed after installation; the launcher menu
reads its resources from the game's own save: storage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE / "package"


def detect_kit() -> Path:
    """Works both beside a kit clone and inside it (kit/izlauncher/)."""
    for base in (HERE, HERE.parent, HERE.parent.parent):
        if (base / "save-tools" / "send_js.py").is_file() or (base / "docs" / "SAVE-BACKUP.md").is_file():
            return base
    return HERE.parent / "kit"


DEFAULT_KIT = detect_kit()
CHUNK = 65536  # 64 KiB -> 131072 hex chars per loader script
DEFAULT_TRIGGER = "save:/saves/Single/IZ2S.Civ7Save"
KIT_TRIGGER = "save:/saves/Single/XSTRIG.Civ7Save"
CAPSULE_DIR = "save:/IZ2S/launcher022"
BACKUP_ROOT = "save:/IZ2SOffline"

# fs offsets relative to sdk_base, exactly the set documented by civswitch-kit
# in kit/docs/SAVE-BACKUP.md (all validated by the kit's own restore flow).
FS_OFFSETS = {
    "ReadFile": "0xa5bf0",
    "WriteFile": "0xa5e00",
    "SetFileSize": "0xa6020",
    "CreateFile": "0xa6700",
    "DeleteFile": "0xa6710",
    "CreateDir": "0xa6890",
    "CloseFile": "0xa5a70",
    "OpenFile": "0xa78a0",
    "Commit": "0xa7de0",
    "OpenDir": "0xa7bb0",
    "ReadDir": "0xa5840",
    "CloseDir": "0xa57b0",
}


# --------------------------------------------------------------------------
# Console-side runtime (kit style: sdk_base / call_rop / malloc / log).
# Loaded once per game process and kept in window.__izKitLauncher.
# --------------------------------------------------------------------------
RUNTIME = r"""
(async function () {
"use strict";
if (window.__izKitLauncher) {
    await log("IZK_REPLY " + JSON.stringify(window.__izKitLauncher.state()));
    return;
}
var F = {
    open:     sdk_base + 0xa78a0n,
    close:    sdk_base + 0xa5a70n,
    read:     sdk_base + 0xa5bf0n,
    write:    sdk_base + 0xa5e00n,
    size:     sdk_base + 0xa6020n,
    create:   sdk_base + 0xa6700n,
    del:      sdk_base + 0xa6710n,
    mkdir:    sdk_base + 0xa6890n,
    commit:   sdk_base + 0xa7de0n,
    opendir:  sdk_base + 0xa7bb0n,
    readdir:  sdk_base + 0xa5840n,
    closedir: sdk_base + 0xa57b0n
};
var p = malloc(0x12000);
if (!p) throw new Error("IZlauncher: native buffer allocation failed");
var PATH = p, PATH2 = p + 0x400n, HOUT = p + 0x800n, WO = p + 0x810n, DATA = p + 0x1000n;
write32(WO, 1n);
var CHUNK = 65536;
var st = { workPath: null, workHandle: 0n, total: 0, written: 0, published: null,
           oldHandle: 0n, oldSize: 0, target: null, backup: null };

function u32(r) { return BigInt.asUintN(32, r); }
function code(r) { return "0x" + u32(r).toString(16).padStart(8, "0"); }
function call(name, args) { return u32(call_rop.apply(null, [F[name]].concat(args))); }
function ok(name, args) { var r = call(name, args); if (r !== 0n) throw new Error(name + " failed " + code(r)); return r; }
function pathbuf(base, value) {
    if (typeof value !== "string" || value.length < 1 || value.length >= 999) throw new Error("invalid save path");
    for (var i = 0; i < value.length; i++) write8(base + BigInt(i), BigInt(value.charCodeAt(i) & 0xff));
    write8(base + BigInt(value.length), 0n);
    return base;
}
function existsDir(path) {
    var r = call("opendir", [HOUT, pathbuf(PATH2, path), 3n]);
    if (r !== 0n) return false;
    var h = read64(HOUT);
    try { call("closedir", [h]); } catch (e) {}
    return true;
}
function parentOf(full) {
    var slash = full.lastIndexOf("/");
    return slash < 0 ? "" : full.slice(0, slash);
}
function mkdirs(path) {
    if (!path) return;
    var cut = path.indexOf(":/");
    var base = cut >= 0 ? path.slice(0, cut + 1) : "";
    var rest = cut >= 0 ? path.slice(cut + 2) : path;
    var parts = rest.split("/"), acc = base;
    for (var i = 0; i < parts.length; i++) {
        if (!parts[i]) continue;
        acc += "/" + parts[i];
        var r = call("mkdir", [pathbuf(PATH2, acc)]);
        if (r === 0n) continue;
        if (!existsDir(acc)) throw new Error("mkdir " + acc + " " + code(r));
    }
}
function fileInfo(full) {
    var slash = full.lastIndexOf("/");
    if (slash < 0) return null;
    var dir = full.slice(0, slash), name = full.slice(slash + 1);
    var h = malloc(8), count = malloc(8), entries = malloc(0x310 * 16);
    try {
        var r = call("opendir", [h, pathbuf(PATH2, dir), 3n]);
        if (r !== 0n) return null;
        var dh = read64(h), found = null;
        try {
            for (;;) {
                write64(count, 0n);
                r = call("readdir", [count, entries, dh, 16n]);
                if (r !== 0n) break;
                var n = Number(read64(count));
                if (!n) break;
                for (var i = 0; i < n; i++) {
                    var e = entries + BigInt(i * 0x310);
                    var s = "";
                    for (var j = 0; j < 0x300; j++) {
                        var c = Number(read8(e + BigInt(j)));
                        if (!c) break;
                        s += String.fromCharCode(c);
                    }
                    if (s === name) found = { name: s, size: Number(read64(e + 0x308n)),
                                              type: Number(read32(e + 0x304n) & 0xffn) };
                }
                if (n < 16) break;
            }
        } finally { try { call("closedir", [dh]); } catch (e) {} }
        return found;
    } finally { free(entries); free(count); free(h); }
}
function openRead(path) {
    var r = call("open", [HOUT, pathbuf(PATH, path), 1n]);
    return { ok: r === 0n, code: r, handle: r === 0n ? read64(HOUT) : 0n };
}
function openWrite(path) {
    ok("open", [HOUT, pathbuf(PATH, path), 6n]);
    return read64(HOUT);
}

// SHA-256 over a Uint8Array (same portable implementation the launcher capsule
// uses).  Used for full on-console verification, so no bulk readback traffic.
function sha256hex(input) {
    var k = [0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
             0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
             0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
             0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
             0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
             0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
             0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
             0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
    var h = [0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
    var size = Math.ceil((input.length + 9) / 64) * 64;
    var b = new Uint8Array(size), v = new DataView(b.buffer), w = new Uint32Array(64);
    function ro(x, n) { return (x >>> n) | (x << (32 - n)); }
    b.set(input); b[input.length] = 128;
    v.setBigUint64(size - 8, BigInt(input.length) * 8n, false);
    for (var off = 0; off < size; off += 64) {
        for (var i = 0; i < 16; i++) w[i] = v.getUint32(off + i * 4, false);
        for (var i = 16; i < 64; i++) {
            var x = w[i - 15], y = w[i - 2];
            w[i] = (w[i - 16] + (ro(x,7) ^ ro(x,18) ^ (x >>> 3)) + w[i - 7] +
                    (ro(y,17) ^ ro(y,19) ^ (y >>> 10))) >>> 0;
        }
        var a = h[0], c = h[1], d = h[2], e = h[3], f = h[4], g = h[5], j = h[6], l = h[7];
        for (var i = 0; i < 64; i++) {
            var t = (l + (ro(f,6) ^ ro(f,11) ^ ro(f,25)) + ((f & g) ^ (~f & j)) + k[i] + w[i]) >>> 0;
            var u = ((ro(a,2) ^ ro(a,13) ^ ro(a,22)) + ((a & c) ^ (a & d) ^ (c & d))) >>> 0;
            l = j; j = g; g = f; f = (e + t) >>> 0; e = d; d = c; c = a; a = (t + u) >>> 0;
        }
        h[0] = (h[0] + a) >>> 0; h[1] = (h[1] + c) >>> 0; h[2] = (h[2] + d) >>> 0; h[3] = (h[3] + e) >>> 0;
        h[4] = (h[4] + f) >>> 0; h[5] = (h[5] + g) >>> 0; h[6] = (h[6] + j) >>> 0; h[7] = (h[7] + l) >>> 0;
    }
    var out = "";
    for (var i = 0; i < 8; i++) out += h[i].toString(16).padStart(8, "0");
    return out;
}
function hashFile(path, size) {
    if (!Number.isSafeInteger(size) || size < 0 || size > 16 * 1024 * 1024) throw new Error("invalid hash size");
    var f = openRead(path);
    if (!f.ok) throw new Error("open " + path + " " + code(f.code));
    try {
        var out = new Uint8Array(size), at = 0;
        while (at < size) {
            var n = Math.min(CHUNK, size - at);
            ok("read", [f.handle, BigInt(at), DATA, BigInt(n)]);
            for (var i = 0; i < n; i++) out[at + i] = Number(read8(DATA + BigInt(i)));
            at += n;
        }
        return sha256hex(out);
    } finally { try { call("close", [f.handle]); } catch (e) {} }
}
function copyFile(src, dst, size) {
    var f = openRead(src);
    if (!f.ok) throw new Error("open source " + src + " " + code(f.code));
    try {
        mkdirs(parentOf(dst));
        var del = call("del", [pathbuf(PATH2, dst)]);
        if (del !== 0n && u32(del) !== 0x202n) throw new Error("delete " + dst + " " + code(del));
        var cr = call("create", [pathbuf(PATH2, dst), BigInt(size)]);
        if (cr !== 0n && u32(cr) !== 0x402n) throw new Error("create " + dst + " " + code(cr));
        var w = openWrite(dst);
        try {
            ok("size", [w, BigInt(size)]);
            var at = 0;
            while (at < size) {
                var n = Math.min(CHUNK, size - at);
                ok("read", [f.handle, BigInt(at), DATA, BigInt(n)]);
                ok("write", [w, BigInt(at), DATA, BigInt(n), WO]);
                at += n;
            }
        } finally { try { call("close", [w]); } catch (e) {} }
    } finally { try { call("close", [f.handle]); } catch (e) {} }
}
function commitSave() {
    var r = call("commit", [pathbuf(PATH2, "save")]);
    if (r !== 0n) throw new Error("Commit(save) " + code(r));
}
function state() {
    return { ready: true, work: st.workPath, total: st.total, written: st.written,
             published: st.published, oldSize: st.oldSize, target: st.target };
}

var api = {
    state: state,
    offsets: function () { return F; },

    inspect: function (full) {
        st.target = full;
        var info = fileInfo(full);
        var f = openRead(full);
        if (!f.ok) {
            if (u32(f.code) === 0x202n) return { exists: false, target: full };
            throw new Error("inspect " + full + " " + code(f.code));
        }
        if (!info) { call("close", [f.handle]); throw new Error("cannot size " + full); }
        st.oldHandle = f.handle;
        st.oldSize = info.size;
        return { exists: true, target: full, size: info.size, sha256: hashFile(full, info.size) };
    },

    backup: function (dest) {
        if (!st.oldHandle || !st.target) return { exists: false };
        var size = st.oldSize;
        mkdirs(parentOf(dest));
        var del = call("del", [pathbuf(PATH2, dest)]);
        if (del !== 0n && u32(del) !== 0x202n) throw new Error("delete backup " + code(del));
        var cr = call("create", [pathbuf(PATH2, dest), BigInt(size)]);
        if (cr !== 0n && u32(cr) !== 0x402n) throw new Error("create backup " + code(cr));
        var w = openWrite(dest);
        try {
            ok("size", [w, BigInt(size)]);
            var at = 0;
            while (at < size) {
                var n = Math.min(CHUNK, size - at);
                ok("read", [st.oldHandle, BigInt(at), DATA, BigInt(n)]);
                ok("write", [w, BigInt(at), DATA, BigInt(n), WO]);
                at += n;
            }
        } finally { try { call("close", [w]); } catch (e) {} }
        try { call("close", [st.oldHandle]); } catch (e) {}
        st.oldHandle = 0n;
        commitSave();
        var digest = hashFile(dest, size);
        st.backup = { path: dest, bytes: size, sha256: digest };
        return { exists: true, path: dest, bytes: size, sha256: digest };
    },

    begin: function (path, size) {
        if (st.workHandle) throw new Error("an upload is already in progress; restart the game");
        if (!Number.isSafeInteger(size) || size < 1 || size > 16 * 1024 * 1024) throw new Error("invalid upload size");
        mkdirs(parentOf(path));
        var del = call("del", [pathbuf(PATH2, path)]);
        if (del !== 0n && u32(del) !== 0x202n) throw new Error("delete staged " + code(del));
        var cr = call("create", [pathbuf(PATH2, path), BigInt(size)]);
        if (cr !== 0n && u32(cr) !== 0x402n) throw new Error("create staged " + code(cr));
        st.workPath = path; st.total = size; st.written = 0; st.published = null;
        st.workHandle = openWrite(path);
        ok("size", [st.workHandle, BigInt(size)]);
        return state();
    },

    chunk: function (offset, hex) {
        if (!st.workHandle) throw new Error("no upload in progress");
        if (typeof hex !== "string" || !/^([0-9a-f]{2})*$/.test(hex)) throw new Error("invalid hex chunk");
        var bytes = hex.length / 2;
        if (offset !== st.written || st.written + bytes > st.total) throw new Error("invalid chunk order");
        for (var i = 0; i < bytes; i++) write8(DATA + BigInt(i), BigInt(parseInt(hex.slice(i * 2, i * 2 + 2), 16)));
        ok("write", [st.workHandle, BigInt(offset), DATA, BigInt(bytes), WO]);
        st.written += bytes;
        return { written: st.written };
    },

    seal: function () {
        if (!st.workHandle || st.written !== st.total) throw new Error("upload is incomplete");
        call("close", [st.workHandle]); st.workHandle = 0n;
        var info = fileInfo(st.workPath);
        if (!info || info.size !== st.total) throw new Error("staged size mismatch");
        return { size: info.size, sha256: hashFile(st.workPath, st.total) };
    },

    publish: function (target) {
        if (!st.workPath || st.written !== st.total) throw new Error("nothing staged");
        if (st.workHandle) { call("close", [st.workHandle]); st.workHandle = 0n; }
        copyFile(st.workPath, target, st.total);
        commitSave();
        st.published = target;
        return { target: target, bytes: st.total, sha256: hashFile(target, st.total), committed: true };
    },

    discard: function () {
        var path = st.workPath;
        if (st.workHandle) { try { call("close", [st.workHandle]); } catch (e) {} st.workHandle = 0n; }
        if (path) { try { call("del", [pathbuf(PATH2, path)]); } catch (e) {} }
        st.workPath = null; st.total = 0; st.written = 0; st.published = null;
        return state();
    },

    readHex: function (path, offset, count) {
        // small bounded read for the optional --pull-backup path (log() safe)
        if (!Number.isInteger(count) || count < 0 || count > 512) throw new Error("invalid read length");
        var f = openRead(path);
        if (!f.ok) throw new Error("open " + path + " " + code(f.code));
        try {
            ok("read", [f.handle, BigInt(offset), DATA, BigInt(count)]);
            var hex = "";
            for (var i = 0; i < count; i++) hex += Number(read8(DATA + BigInt(i))).toString(16).padStart(2, "0");
            return hex;
        } finally { try { call("close", [f.handle]); } catch (e) {} }
    },

    restore: function (backupPath, target, expectedSha, expectedBytes) {
        var info = fileInfo(backupPath);
        if (!info) throw new Error("backup not found on console: " + backupPath);
        if (info.size !== expectedBytes) throw new Error("backup size mismatch: " + info.size);
        var digest = hashFile(backupPath, expectedBytes);
        if (digest !== expectedSha) throw new Error("backup SHA-256 mismatch: " + digest);
        copyFile(backupPath, target, expectedBytes);
        commitSave();
        var after = hashFile(target, expectedBytes);
        if (after !== expectedSha) throw new Error("restored SHA-256 mismatch: " + after);
        return { target: target, bytes: expectedBytes, sha256: after, committed: true };
    }
};
window.__izKitLauncher = api;
await log("IZK_REPLY " + JSON.stringify(api.state()));
})();
"""


# --------------------------------------------------------------------------
# Host side
# --------------------------------------------------------------------------
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def send(host: str, port: int, code: str, timeout: float) -> str:
    """One script per half-closed connection, exactly like save-tools/send_js.py."""
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


class Console:
    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def raw(self, code: str, timeout: float | None = None) -> str:
        return send(self.host, self.port, code, timeout or self.timeout)

    def probe(self) -> None:
        nonce = "IZK_PROBE_" + uuid.uuid4().hex
        out = self.raw("log('%s')" % nonce, timeout=10)
        if nonce not in out:
            raise RuntimeError(
                "Remote JS Loader is not answering on %s:%d.\n"
                "Arm it first: Civ7 -> Load Game -> XSTRIG row -> 'Awaiting payload at <IP>:9026'."
                % (self.host, self.port)
            )

    def load_runtime(self) -> dict:
        out = self.raw(RUNTIME, timeout=60)
        state = parse_reply(out)
        if not state.get("ready"):
            raise RuntimeError("console runtime did not report ready")
        if state.get("work"):
            raise RuntimeError(
                "a previous upload is still staged on the console (%s); restart Civ7 before retrying"
                % state["work"]
            )
        return state

    def call(self, method: str, args: list | None = None, timeout: float | None = None) -> dict:
        args = args or []
        code = (
            "(async function(){try{var r=window.__izKitLauncher[%s].apply(window.__izKitLauncher,%s);"
            "if(r&&typeof r.then==='function')r=await r;"
            "await log('IZK_REPLY '+JSON.stringify(r));}"
            "catch(e){await log('IZK_ERROR '+JSON.stringify({message:String(e&&e.message||e),"
            "stack:String(e&&e.stack||'')}));}})()"
            % (json.dumps(method), json.dumps(args))
        )
        return parse_reply(self.raw(code, timeout=timeout))


def parse_reply(output: str) -> dict:
    replies = re.findall(r"IZK_REPLY (.*)", output)
    errors = re.findall(r"IZK_ERROR (.*)", output)
    if errors:
        try:
            detail = json.loads(errors[-1])
        except json.JSONDecodeError:
            detail = {"message": errors[-1]}
        raise RuntimeError("console: %s" % detail.get("message", detail))
    if not replies:
        raise RuntimeError(
            "console did not confirm the request; do not replay installation.\n"
            "Output tail: %r" % output[-400:]
        )
    try:
        return json.loads(replies[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError("invalid console reply: %r" % replies[-1]) from exc


def load_manifest() -> tuple[dict, Path, Path]:
    manifest_path = PACKAGE / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    save = PACKAGE / manifest["save"]
    capsule = PACKAGE / manifest["capsule"]["file"]
    if not save.is_file():
        raise SystemExit("missing trigger save: %s" % save)
    if not capsule.is_file():
        raise SystemExit("missing menu capsule: %s" % capsule)
    return manifest, save, capsule


def validate_local(manifest: dict, save: Path, capsule: Path) -> None:
    problems = []
    if save.stat().st_size != manifest["saveBytes"]:
        problems.append("trigger size %d != %d" % (save.stat().st_size, manifest["saveBytes"]))
    if sha256_file(save) != manifest["saveSha256"]:
        problems.append("trigger SHA-256 mismatch")
    if capsule.stat().st_size != manifest["capsule"]["bytes"]:
        problems.append("capsule size %d != %d" % (capsule.stat().st_size, manifest["capsule"]["bytes"]))
    if sha256_file(capsule) != manifest["capsule"]["sha256"]:
        problems.append("capsule SHA-256 mismatch")
    boot = PACKAGE / manifest.get("source", "boot.js")
    if boot.is_file() and manifest.get("sourceSha256") and sha256_file(boot) != manifest["sourceSha256"]:
        problems.append("boot.js SHA-256 mismatch")
    if problems:
        raise SystemExit("local package validation failed:\n  - " + "\n  - ".join(problems))


def check_kit(kit: Path) -> None:
    doc = kit / "docs" / "SAVE-BACKUP.md"
    if not doc.is_file():
        print("[warn] kit not found at %s (pass --kit); protocol offsets are still built in" % kit)
        return
    text = doc.read_text(encoding="utf-8", errors="replace")
    missing = [name for name, off in FS_OFFSETS.items() if off not in text]
    if missing:
        print("[warn] kit docs do not list offsets for: %s (verify against your kit version)" % ", ".join(missing))
    else:
        print("[ok] civswitch-kit fs offsets match: %s" % doc)


def upload(console: Console, path: str, data: bytes, label: str) -> dict:
    total = len(data)
    console.call("begin", [path, total], timeout=60)
    sent = 0
    for at in range(0, total, CHUNK):
        part = data[at : at + CHUNK]
        console.call("chunk", [at, part.hex()], timeout=120)
        sent = at + len(part)
        if sent == total or sent % (CHUNK * 8) == 0:
            print("  %s: %d / %d" % (label, sent, total))
    return console.call("seal", [], timeout=self_timeout(console, total))


def self_timeout(console: Console, total: int) -> float:
    # hashing is linear in file size on the console; keep a generous bound
    return max(console.timeout, 60 + total / 20000)


def install(args: argparse.Namespace) -> int:
    manifest, save, capsule = load_manifest()
    validate_local(manifest, save, capsule)
    if args.check:
        print(json.dumps({
            "version": manifest["version"],
            "triggerBytes": manifest["saveBytes"],
            "triggerSha256": manifest["saveSha256"],
            "capsuleBytes": manifest["capsule"]["bytes"],
            "capsuleSha256": manifest["capsule"]["sha256"],
            "capsuleTarget": manifest["capsule"]["target"],
            "defaultTarget": DEFAULT_TRIGGER,
            "kit": str(args.kit),
        }, indent=2))
        if args.ip:
            console = Console(args.ip, args.port, args.timeout)
            console.probe()
            print("[ok] loader online at %s:%d" % (args.ip, args.port))
        return 0

    if not args.ip:
        raise SystemExit("--ip is required (or use --check)")

    trigger = KIT_TRIGGER if args.replace_kit_trigger else (args.name or DEFAULT_TRIGGER)
    trigger = trigger if trigger.startswith("save:/") else "save:/saves/Single/" + trigger
    if not trigger.startswith("save:/saves/Single/"):
        raise SystemExit("trigger path must live under save:/saves/Single/")

    if args.dry_run:
        print("plan:")
        print("  capsule -> %s (%d bytes)" % (manifest["capsule"]["target"], manifest["capsule"]["bytes"]))
        print("  trigger -> %s (%d bytes)" % (trigger, manifest["saveBytes"]))
        print("  backup  -> %s/<uuid>/previous.bin" % BACKUP_ROOT)
        return 0

    console = Console(args.ip, args.port, args.timeout)
    console.probe()
    print("[ok] loader online at %s:%d" % (args.ip, args.port))
    console.load_runtime()
    print("[ok] kit-native fs runtime loaded on console")

    receipt_id = str(uuid.uuid4())
    receipt_dir = HERE / "receipts" / receipt_id
    receipt_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt = {
        "id": receipt_id,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": args.ip,
        "port": args.port,
        "launcher": {
            "version": manifest["version"],
            "saveBytes": manifest["saveBytes"],
            "saveSha256": manifest["saveSha256"],
        },
        "trigger": {"target": trigger, "bytes": manifest["saveBytes"],
                    "sha256": manifest["saveSha256"], "installed": False},
        "capsule": None,
        "backup": {"exists": False},
        "phase": "preflight",
    }
    receipt_path = receipt_dir / "receipt.json"

    def record() -> None:
        receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    record()

    try:
        # --- 1. immutable menu capsule -----------------------------------
        if not args.no_capsule:
            target = manifest["capsule"]["target"]
            print("=== capsule ===")
            print("target: %s (%d bytes)" % (target, capsule.stat().st_size))
            receipt["phase"] = "capsule"
            receipt["capsule"] = {"target": target, "bytes": capsule.stat().st_size,
                                  "sha256": manifest["capsule"]["sha256"], "installed": False}
            record()
            staged = target.rsplit("/", 1)[0] + "/.menu-staged.bin"
            got = upload(console, staged, capsule.read_bytes(), "capsule")
            if got["sha256"] != manifest["capsule"]["sha256"]:
                raise RuntimeError("capsule SHA-256 mismatch on console: %s" % got["sha256"])
            print("[ok] capsule verified on console: %s" % got["sha256"])
            published = console.call("publish", [target], timeout=console.timeout)
            if published["sha256"] != manifest["capsule"]["sha256"]:
                raise RuntimeError("capsule final path mismatch: %s" % published["sha256"])
            console.call("discard")
            receipt["capsule"]["installed"] = True
            receipt["capsule"]["verified"] = True
            record()
            print("[ok] capsule published and committed")
        else:
            print("[skip] capsule (--no-capsule)")

        # --- 2. back up the previous trigger ------------------------------
        print("=== trigger ===")
        info = console.call("inspect", [trigger], timeout=console.timeout)
        if info.get("exists"):
            print("existing trigger: %d bytes, sha256 %s" % (info["size"], info["sha256"]))
            backup_path = "%s/%s/previous.bin" % (BACKUP_ROOT, receipt_id)
            receipt["phase"] = "backup"
            record()
            backup = console.call("backup", [backup_path], timeout=console.timeout)
            receipt["backup"] = {
                "exists": True,
                "consolePath": backup["path"],
                "bytes": backup["bytes"],
                "sha256": backup["sha256"],
                "pcPath": None,
            }
            record()
            print("[ok] previous trigger backed up: %s" % backup_path)
            if args.pull_backup:
                pc_path = receipt_dir / "previous.Civ7Save"
                pull_backup(console, backup["path"], backup["bytes"], pc_path)
                if sha256_file(pc_path) != backup["sha256"]:
                    raise RuntimeError("pulled backup SHA-256 mismatch")
                receipt["backup"]["pcPath"] = str(pc_path)
                record()
                print("[ok] backup pulled to %s" % pc_path)
        else:
            print("no previous trigger at this path (first install)")

        # --- 3. upload and publish the trigger ----------------------------
        staged = "%s/%s/candidate.bin" % (BACKUP_ROOT, receipt_id)
        receipt["phase"] = "staging"
        record()
        save_bytes = save.read_bytes()
        got = upload(console, staged, save_bytes, "trigger")
        if got["sha256"] != manifest["saveSha256"]:
            raise RuntimeError("trigger SHA-256 mismatch on console: %s" % got["sha256"])
        print("[ok] trigger verified on console: %s" % got["sha256"])
        receipt["phase"] = "publishing"
        record()
        published = console.call("publish", [trigger], timeout=console.timeout)
        if published["sha256"] != manifest["saveSha256"]:
            raise RuntimeError("trigger final path mismatch: %s" % published["sha256"])
        console.call("discard")
        receipt["trigger"]["installed"] = True
        receipt["phase"] = "installed"
        receipt["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        record()
        print("[ok] trigger published and committed")
        print()
        print("INSTALL DONE. Save written: %s" % trigger)
        print("Close Civ7 fully (HOME/X), then start it again and open Load Game.")
        print("The launcher row now boots the menu from local save: storage - no PC needed.")
        print("Receipt: %s" % receipt_path)
        return 0
    except Exception as exc:  # keep the receipt for forensics
        receipt["phase"] = "failed"
        receipt["error"] = str(exc)
        record()
        raise


def pull_backup(console: Console, path: str, size: int, dest: Path) -> None:
    """Optional slow PC copy: log() is safe for ~512 bytes per line."""
    data = bytearray()
    step = 512
    for at in range(0, size, step):
        hex_text = console.call("readHex", [path, at, min(step, size - at)], timeout=60)
        data += bytes.fromhex(hex_text)
        if (at // step) % 128 == 0:
            print("  pull-backup: %d / %d" % (len(data), size))
    if len(data) != size:
        raise RuntimeError("pull-backup size mismatch: %d != %d" % (len(data), size))
    dest.write_bytes(bytes(data))


def restore(args: argparse.Namespace) -> int:
    receipt_path = Path(args.restore).expanduser().resolve()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    backup = receipt.get("backup") or {}
    if not backup.get("exists") or not backup.get("consolePath"):
        raise SystemExit("receipt has no console backup of the previous trigger; nothing to restore")
    target = receipt["trigger"]["target"]
    if args.name:
        target = args.name if args.name.startswith("save:/") else "save:/saves/Single/" + args.name
    console = Console(args.ip, args.port, args.timeout)
    console.probe()
    print("[ok] loader online at %s:%d" % (args.ip, args.port))
    console.load_runtime()
    print("restoring %s (%d bytes, sha256 %s)"
          % (backup["consolePath"], backup["bytes"], backup["sha256"]))
    result = console.call(
        "restore",
        [backup["consolePath"], target, backup["sha256"], backup["bytes"]],
        timeout=self_timeout(console, backup["bytes"]),
    )
    print("RESTORE DONE. %s <- %s (%d bytes, sha256 %s)"
          % (result["target"], backup["consolePath"], result["bytes"], result["sha256"]))
    print("Restart Civilization VII and open Load Game.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install/restore IZlauncher 0.22 (Civ7) through a civswitch-kit loader.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python install.py --ip 10.42.0.20 --check\n"
            "  python install.py --ip 10.42.0.20\n"
            "  python install.py --ip 10.42.0.20 --replace-kit-trigger\n"
            "  python install.py --ip 10.42.0.20 --restore receipts/<uuid>/receipt.json\n"
        ),
    )
    parser.add_argument("--ip", help="console LAN address (loader must be armed)")
    parser.add_argument("--port", type=int, default=9026)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--kit", type=Path, default=DEFAULT_KIT, help="civswitch-kit directory")
    parser.add_argument("--name", default=None,
                        help="trigger save file name under save:/saves/Single/ (default: IZ2S.Civ7Save)")
    parser.add_argument("--replace-kit-trigger", action="store_true",
                        help="write to XSTRIG.Civ7Save instead (kit's canonical trigger path)")
    parser.add_argument("--no-capsule", action="store_true", help="do not install/refresh the menu capsule")
    parser.add_argument("--pull-backup", action="store_true", help="also copy the previous trigger to the PC (slow)")
    parser.add_argument("--restore", metavar="RECEIPT", help="restore the previous trigger recorded in a receipt")
    parser.add_argument("--check", action="store_true", help="validate local package and, with --ip, the loader")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without touching the console")
    args = parser.parse_args(argv)

    check_kit(args.kit)
    if args.restore:
        if not args.ip:
            parser.error("--restore requires --ip")
        return restore(args)
    return install(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted; no automatic retry", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print("\nFAILED: %s" % exc, file=sys.stderr)
        print("The loader will not be replayed automatically. Restart Civ7 before another attempt.", file=sys.stderr)
        sys.exit(1)
