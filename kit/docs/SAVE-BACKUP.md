# Civ7 存档备份 / 恢复

## 结论

- 已把 `save:/saves` **全量备份**到 PC，并**实测验证过可恢复**：恢复后重新 dump，7 个文件的 SHA-256 与备份全部一致。
- 备份内容是「固化完成、loader 可用」的纯净状态快照。后续 slapah FS acquisition 会在 `save:/` 根写 `/NS2_GAP_*`、`/main`、`/main.npdm`，与 trigger 存档同分区 —— 出问题用这份恢复。

## 备份位置

| 内容 | 路径（相对本包，时间戳以实际运行为准） |
|---|---|
| 单文件 trigger save | `save-tools\backups\2026-11-09_142619+0800\XSTRIG.Civ7Save` + `metadata.json` |
| 全量 save:/saves 快照（7 文件） | `save-tools\backups\2026-11-09_142719+0800\save_tree\...` + `manifest.json` |
| 恢复后复核快照（对照用） | `save-tools\backups\2026-11-09_143034+0800\manifest.json` |

> `save-tools\backups\` 不入库（见 `.gitignore`）。

## 文件清单（备份 = 当前主机状态，已逐一复核）

| 控制台路径 | 字节 | SHA-256 |
|---|---|---|
| `save:/saves/Single/XSTRIG.Civ7Save` | 1,182,991 | `7128d555b8f8c0ae7293ee58e12f789d154c100f5cb0895dbc2da078b7adb67c` |
| `save:/saves/AppOptions.txt` | 7,461 | `22ae1440d31d4429d480d86a6407b91726ec0e188b57e9a0e02699c062d09fb6` |
| `save:/saves/UserOptions.txt` | 6,397 | `30df131aaf135d7a333c5e8884ac930bf7c974e61cbc7d0717677940e2cbb156` |
| `save:/saves/SoundOpts.txt` | 662 | `22a699a195a7a6dca4cc61461296b1fb94112c0dfa18184ae5874c7ddae5ea64` |
| `save:/saves/TutorialOptions.txt` | 521 | `6e82671d1dc1a6646ec3ac9118f9229c2359f332801500d95a8969c601667c7e` |
| `save:/saves/NetworkOptions.txt` | 486 | `4d4cbd5314ba94c527fd4655d517888e34d604857109ff7a1e2491212ce30bdb` |
| `save:/saves/HallofFame.sqlite` | 90,112 | `f3f8909aa410f22d4f1033967f336885fc80abc2e624c2071185c6dab002adac` |

合计 7 个文件 / **1,288,630 B**。

说明：`XSTRIG.Civ7Save` 含当前 loader payload；模板 `save_template.bin` 是 1,159,730 B，差值来自 XSSP stage 替换 `currentTurnDate` 记录后的长度变化（installer 语义）。

## 恢复方法（已实测）

```powershell
# 在包的根目录执行
python -u .\save-tools\restore_save.py .\save-tools\backups\2026-11-09_142719+0800 <S2_IP>
# 预演不发送：加 --dry-run
# 只恢复匹配项：加 --only XSTRIG
```

流程：本地把文件 b64 后按 400,000 字符分块经多次 loader 连接存进 `window.__restore`，再发一条 apply payload：`F_CreateFile` → `F_OpenFile(flags 6)` → `F_SetFileSize` → `F_WriteFile` → `F_CloseFile`，最后 `F_Commit("save")`。与官方 `installer-creator/install.py` 写存档同一组原语。

## 实测时间线

| 时间 | 动作 | 结果 |
|---|---|---|
| 14:26:19 | 单文件 dump（2,311 chunks） | PASS，sha256 `7128d5…d67c`，magic `CIV7` 校验通过 |
| 14:27:19 | 全量 snapshot（7 文件 / 2,517 chunks） | PASS，manifest 落盘 |
| ≈14:30 | `restore_save.py` 全量写回 | 6/7 文件写入成功（含 1.18 MB trigger），HallofFame.sqlite 被锁失败 |
| 14:30:34 | 复核 snapshot | **7 个 SHA-256 全部与备份一致** → 恢复闭环成立 |

证据图（未随包分发）：`snapshot-run.png`（快照流）、`restore-run.png`（恢复日志）、`dump-start.png`（save 目录清单）。

## 已知限制

- `HallofFame.sqlite` 被游戏进程持有：`CreateFile` 返回 `0x402`（路径已存在）、`OpenFile(6)` 返回 `0xE02`，loader 运行期间无法删除/覆盖。其内容本来就与备份一致，不影响备份有效性；将来若真需要恢复这个文件，只能走 slapah 的 ns2jb Stage2 FS 任意写，或在游戏内重置声望数据。
- 恢复要求 loader 在 `:9026` 且游戏停在 loader 页面；写回后 `Commit("save")` 即生效，本次未重启即复核通过。
- 恢复会「删除 + 重写」目标文件；trigger 若写坏，可先用上游 slapah/CivSwitch 的 `installer-creator/install.py` 或 S1 的 ldn-nx NRO 重装拿到 loader，再恢复本备份。

## 工具（`save-tools\`）

| 文件 | 用途 |
|---|---|
| `send_js.py` | 向 `:9026` 发任意 JS payload（其余脚本的发送层） |
| `payloads\save_dump.js` | 单文件只读导出的 console 侧 payload |
| `payloads\save_snapshot.js` + `dump_save_tree.py` | `save:/saves` 一层目录全量快照（SNAP 帧 + manifest） |
| `restore_save.py` | 按 manifest 写回，支持 `--dry-run` / `--only` |
| `probe_9026.py` | 探测 `:9026` 是否在线（少用，见 README §8） |
| `trigger-recreate\` | 重建好的触发存档 `XSTRIG.Civ7Save` + `manifest.json` |

fs 原语偏移（均为 `sdk_base + 常量`）：ReadFile `0xa5bf0`、WriteFile `0xa5e00`、SetFileSize `0xa6020`、CreateFile `0xa6700`、DeleteFile `0xa6710`、CreateDir `0xa6890`、CloseFile `0xa5a70`、OpenFile `0xa78a0`、Commit `0xa7de0`、OpenDir `0xa7bb0`、ReadDir `0xa5840`、CloseDir `0xa57b0`。
