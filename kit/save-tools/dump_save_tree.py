"""Host-side receiver for save_snapshot.js (SNAP frames).

Writes every streamed console file under save-tools/backups/<timestamp>/save_tree/
and emits manifest.json with per-file sizes and SHA-256 digests.

Usage:
  python dump_save_tree.py <console_ip> [port]
"""
from __future__ import annotations

import hashlib
import json
import socket
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
PAYLOAD = BASE / "payloads" / "save_snapshot.js"
BACKUPS = BASE / "backups"
TIMEOUT = 1800
CHUNK_SIZE = 512


class SnapshotReceiver:
    def __init__(self, backups_dir: Path) -> None:
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S%z")
        self.root = backups_dir / stamp
        self.files: list[dict] = []
        self.current: dict | None = None
        self.data: bytearray | None = None
        self.chunks = 0

    def begin(self, meta: dict) -> list[str]:
        if self.current is not None:
            raise RuntimeError("SNAP BEGIN while a file is still active")
        size = int(meta["size"])
        self.current = meta
        self.data = bytearray(size)
        self.chunks = 0
        return [f"begin {meta['path']} ({size:,} bytes)"]

    def chunk(self, offset_text: str, length_text: str, hex_text: str) -> list[str]:
        if self.data is None or self.current is None:
            raise RuntimeError("SNAP CHUNK before BEGIN")
        offset = int(offset_text, 16)
        length = int(length_text)
        chunk = bytes.fromhex(hex_text)
        if len(chunk) != length:
            raise RuntimeError(f"chunk length mismatch at {offset}")
        if offset != self.chunks * CHUNK_SIZE:
            raise RuntimeError(f"out-of-order chunk at {offset}")
        if offset + length > len(self.data):
            raise RuntimeError(f"chunk at {offset} exceeds declared size")
        self.data[offset : offset + length] = chunk
        self.chunks += 1
        return []

    def end(self, meta: dict) -> list[str]:
        if self.data is None or self.current is None:
            raise RuntimeError("SNAP END before BEGIN")
        path = meta["path"]
        rel = path.replace("save:/", "save/").lstrip("/")
        dest = self.root / "save_tree" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(bytes(self.data))
        digest = hashlib.sha256(self.data).hexdigest()
        entry = {
            "path": path,
            "stored_as": str(dest.relative_to(self.root)),
            "bytes": len(self.data),
            "chunks": self.chunks,
            "sha256": digest,
            "magic": bytes(self.data[:4]).decode("ascii", "replace"),
            "complete": bool(meta.get("complete")),
        }
        self.files.append(entry)
        self.current = None
        self.data = None
        return [f"end   {path} {entry['bytes']:,} bytes sha256={digest}"]

    def error(self, meta: dict) -> list[str]:
        return [f"error {meta.get('path')}: {meta.get('message')}"]

    def handle_line(self, line: str) -> list[str]:
        parts = line.split("|", 4)
        if len(parts) < 3 or parts[0] != "SNAP":
            return []
        kind = parts[1]
        if kind == "BEGIN" and len(parts) >= 3:
            return self.begin(json.loads(parts[2]))
        if kind == "CHUNK" and len(parts) == 5:
            return self.chunk(parts[2], parts[3], parts[4])
        if kind == "END" and len(parts) == 3:
            return self.end(json.loads(parts[2]))
        if kind == "ERROR" and len(parts) >= 3:
            return self.error(json.loads(parts[2]))
        return []

    def finalize(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "capture_utc": datetime.now().astimezone().isoformat(),
            "source": "save:/saves (one directory level)",
            "file_count": len(self.files),
            "total_bytes": sum(f["bytes"] for f in self.files),
            "files": self.files,
        }
        out = self.root / "manifest.json"
        out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return out


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python dump_save_tree.py <console_ip> [port]", file=sys.stderr)
        return 1
    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9026
    code = PAYLOAD.read_text(encoding="utf-8")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    receiver = SnapshotReceiver(BACKUPS)

    with socket.create_connection((host, port), timeout=8) as sock:
        sock.sendall(code.encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)
        sock.settimeout(TIMEOUT)
        buffer = b""
        while True:
            block = sock.recv(65536)
            if not block:
                break
            buffer += block
            while b"\n" in buffer:
                raw, buffer = buffer.split(b"\n", 1)
                line = raw.decode("utf-8", "replace").rstrip("\r")
                if line.startswith("SNAP|"):
                    for message in receiver.handle_line(line):
                        print(message, flush=True)
                elif line:
                    print(line, flush=True)

    if buffer.strip():
        raise RuntimeError("connection ended with an unterminated line")
    if receiver.current is not None:
        raise RuntimeError("connection ended mid-file: " + str(receiver.current.get("path")))
    manifest = receiver.finalize()
    print(f"manifest: {manifest}")
    print(f"files: {len(receiver.files)} total_bytes: {sum(f['bytes'] for f in receiver.files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
