/* Read-only save dump payload for the CivSwitch Remote JS Loader (:9026).
 *
 * Streams save:/saves/Single/XSTRIG.Civ7Save back to the host as SAVE_DUMP
 * frames, using the same wire format as CivSwitch Control Center's Save
 * Extractor.  Only directory lookup plus read-only OpenFile / ReadFile /
 * CloseFile are used; no filesystem mutation happens here.
 */
(async function civSaveDump() {
    "use strict";

    var DIRECTORY = "save:/saves/Single";
    var NAME = "XSTRIG.Civ7Save";
    var PATH = DIRECTORY + "/" + NAME;
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
        return log("SAVE_DUMP|" + kind + "|" + JSON.stringify(data));
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

    try {
        log("[dump] sdk_base=" + sdk_base.toString(16) + " main_base=" + main_base.toString(16));

        var roots = ["save:/saves", DIRECTORY];
        for (var r = 0; r < roots.length; r++) {
            try {
                var listing = listDir(roots[r]);
                log("[dump] " + roots[r] + " -> " + listing.length + " entr" + (listing.length === 1 ? "y" : "ies"));
                for (var i = 0; i < listing.length; i++) {
                    log("[dump]   " + (listing[i].type === 1 ? "file" : "dir ") +
                        " " + listing[i].size + " " + listing[i].name);
                }
            } catch (error) {
                log("[dump] list " + roots[r] + " failed: " + String(error.message || error));
            }
        }

        var size = -1;
        var entries = listDir(DIRECTORY);
        for (var e = 0; e < entries.length; e++) {
            if (entries[e].type === 1 && entries[e].name === NAME) size = entries[e].size;
        }
        if (size < 0) {
            await emit("ERROR", { message: "target save not found: " + PATH });
            return;
        }

        var chunkSize = CHUNK;
        var expectedChunks = Math.ceil(size / chunkSize);
        log("[dump] target " + PATH + " size=" + size + " chunks=" + expectedChunks);

        await emit("BEGIN", {
            version: 1,
            path: PATH,
            size: size,
            chunk_size: chunkSize,
            expected_chunks: expectedChunks,
            policy: "directory lookup plus read-only OpenFile/ReadFile/CloseFile; no filesystem mutations"
        });

        var handleOut = malloc(8);
        var pathBuffer = malloc(0x400);
        var dataBuffer = malloc(chunkSize);
        var fileHandle = null;
        try {
            writePath(pathBuffer, PATH);
            var openResult = BigInt.asUintN(32, call_rop(F_OpenFile, handleOut, pathBuffer, 1n));
            if (openResult !== 0n) throw new Error("OpenFile " + fsCode(openResult));
            fileHandle = read64(handleOut);

            var offset = 0;
            var chunks = 0;
            while (offset < size) {
                var length = Math.min(chunkSize, size - offset);
                var readResult = BigInt.asUintN(32, call_rop(F_ReadFile, fileHandle, BigInt(offset), dataBuffer, BigInt(length)));
                if (readResult !== 0n) throw new Error("ReadFile at " + offset + " " + fsCode(readResult));
                await log("SAVE_DUMP|CHUNK|" + offset.toString(16).padStart(16, "0") + "|" +
                    length + "|" + hexChunk(dataBuffer, length));
                offset += length;
                chunks++;
            }
            await emit("END", { version: 1, bytes: size, chunks: chunks, complete: offset === size && chunks === expectedChunks });
            log("[dump] done: " + size + " bytes in " + chunks + " chunks");
        } finally {
            if (fileHandle !== null) {
                try { call_rop(F_CloseFile, fileHandle); } catch (_) {}
            }
            free(dataBuffer);
            free(pathBuffer);
            free(handleOut);
        }
    } catch (error) {
        try {
            await emit("ERROR", { message: String(error.message || error), stack: String(error.stack || "") });
        } catch (_) {}
        log("[dump] failed: " + String(error.message || error));
    }
})();
