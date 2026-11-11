/* Read-only snapshot payload: walks save:/saves (one directory level) and
 * streams every file back to the host as SNAP frames.
 *
 * Wire format (one line per frame, emitted through log()):
 *   SNAP|BEGIN|{"path":"save:/...","size":N}
 *   SNAP|CHUNK|<offset 16 hex>|<len>|<hex bytes>
 *   SNAP|END|{"path":"...","bytes":N,"chunks":K}
 *   SNAP|ERROR|{"path":"...","message":"..."}
 * Only directory lookup plus read-only OpenFile/ReadFile/CloseFile are used.
 */
(async function civSaveSnapshot() {
    "use strict";

    var CHUNK = 512;
    var F_OpenDir = sdk_base + 0xa7bb0n;
    var F_ReadDir = sdk_base + 0xa5840n;
    var F_CloseDir = sdk_base + 0xa57b0n;
    var F_OpenFile = sdk_base + 0xa78a0n;
    var F_CloseFile = sdk_base + 0xa5a70n;
    var F_ReadFile = sdk_base + 0xa5bf0n;

    function fsCode(value) {
        return "0x" + BigInt.asUintN(32, value).toString(16).padStart(8, "0");
    }

    function emit(kind, data) {
        return log("SNAP|" + kind + "|" + JSON.stringify(data));
    }

    function writePath(buffer, path) {
        for (var i = 0; i < path.length; i++) {
            write8(buffer + BigInt(i), BigInt(path.charCodeAt(i) & 0xff));
        }
        write8(buffer + BigInt(path.length), 0n);
    }

    function nameOf(entry) {
        var name = "";
        for (var i = 0; i < 0x300; i++) {
            var value = Number(read8(entry + BigInt(i)));
            if (value === 0) break;
            name += String.fromCharCode(value);
        }
        return name;
    }

    function listDir(directory) {
        var BATCH = 16;
        var handleOut = malloc(8);
        var countOut = malloc(8);
        var pathBuffer = malloc(0x400);
        var entries = malloc(0x310 * BATCH);
        var handle = null;
        var out = [];
        try {
            writePath(pathBuffer, directory);
            var result = BigInt.asUintN(32, call_rop(F_OpenDir, handleOut, pathBuffer, 3n));
            if (result !== 0n) throw new Error("OpenDir " + fsCode(result));
            handle = read64(handleOut);
            for (;;) {
                write64(countOut, 0n);
                result = BigInt.asUintN(32, call_rop(F_ReadDir, countOut, entries, handle, BigInt(BATCH)));
                if (result !== 0n) throw new Error("ReadDir " + fsCode(result));
                var count = Number(read64(countOut));
                if (count <= 0) break;
                for (var i = 0; i < count; i++) {
                    var entry = entries + BigInt(i * 0x310);
                    out.push({
                        name: nameOf(entry),
                        type: Number(read32(entry + 0x304n) & 0xffn),
                        size: Number(read64(entry + 0x308n))
                    });
                }
                if (count < BATCH) break;
            }
        } finally {
            if (handle !== null) {
                try { call_rop(F_CloseDir, handle); } catch (_) {}
            }
            free(entries);
            free(pathBuffer);
            free(countOut);
            free(handleOut);
        }
        return out;
    }

    function hexChunk(buffer, length) {
        var output = "";
        for (var i = 0; i < length; i++) {
            output += Number(read8(buffer + BigInt(i))).toString(16).padStart(2, "0");
        }
        return output;
    }

    async function streamFile(path, size) {
        var expectedChunks = Math.ceil(size / CHUNK);
        await emit("BEGIN", { path: path, size: size, chunk_size: CHUNK, expected_chunks: expectedChunks });
        var handleOut = malloc(8);
        var pathBuffer = malloc(0x400);
        var dataBuffer = malloc(CHUNK);
        var fileHandle = null;
        try {
            writePath(pathBuffer, path);
            var openResult = BigInt.asUintN(32, call_rop(F_OpenFile, handleOut, pathBuffer, 1n));
            if (openResult !== 0n) throw new Error("OpenFile " + fsCode(openResult));
            fileHandle = read64(handleOut);
            var offset = 0;
            var chunks = 0;
            while (offset < size) {
                var length = Math.min(CHUNK, size - offset);
                var readResult = BigInt.asUintN(32, call_rop(F_ReadFile, fileHandle, BigInt(offset), dataBuffer, BigInt(length)));
                if (readResult !== 0n) throw new Error("ReadFile at " + offset + " " + fsCode(readResult));
                await log("SNAP|CHUNK|" + offset.toString(16).padStart(16, "0") + "|" +
                    length + "|" + hexChunk(dataBuffer, length));
                offset += length;
                chunks++;
            }
            await emit("END", { path: path, bytes: offset, chunks: chunks, expected_chunks: expectedChunks, complete: offset === size });
            log("[snap] " + path + " " + offset + " bytes");
        } catch (error) {
            await emit("ERROR", { path: path, message: String(error.message || error) });
            log("[snap] " + path + " failed: " + String(error.message || error));
        } finally {
            if (fileHandle !== null) {
                try { call_rop(F_CloseFile, fileHandle); } catch (_) {}
            }
            free(dataBuffer);
            free(pathBuffer);
            free(handleOut);
        }
    }

    try {
        log("[snap] sdk_base=" + sdk_base.toString(16) + " main_base=" + main_base.toString(16));
        var ROOT = "save:/saves";
        var rootEntries = listDir(ROOT);
        for (var i = 0; i < rootEntries.length; i++) {
            var entry = rootEntries[i];
            var path = ROOT + "/" + entry.name;
            if (entry.type === 1) {
                await streamFile(path, entry.size);
            } else if (entry.type === 0) {
                var children = listDir(path);
                for (var j = 0; j < children.length; j++) {
                    if (children[j].type === 1) {
                        await streamFile(path + "/" + children[j].name, children[j].size);
                    }
                }
            }
        }
        log("[snap] done");
    } catch (error) {
        try { await emit("ERROR", { path: "(snapshot)", message: String(error.message || error) }); } catch (_) {}
        log("[snap] failed: " + String(error.message || error));
    }
})();
