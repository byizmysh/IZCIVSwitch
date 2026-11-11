# 上游同步消化：x43x61x69/ns2jb（2026-11-10 下午）

来源：`https://github.com/x43x61x69/ns2jb`（kurumuz/ns2jb 的 11-09 新建衍生，base `81d5bb11`）。
本地存档：`_tmp\x43x61x69-commits\`（5 份 commit JSON + 33 份 patch diff，2026-11-10 13:4x 经 gh-proxy 抓取）。

## 逐提交消化结论

### e3309c35（13:35Z）"Track acquisition batch outcomes and avoid unsafe timeout capture" —— ✅ 已回植
- wave-history.cjs 模块化：hasWindow / markerHit / summarize / positiveOutcome / describe / lastPositiveBatch / failureSummary。
- retryWave 批次账本（report.retryBatches[]）+ wave-summary 日志；requirePositiveMarker 把「positive 全 miss」变成明确抛错（修掉 slapah 版 RUN 17/18 静默完成的 bug）。
- workerFailure.observed==='not-terminated' → workerCaptureSkipped，跳过 capture-workers（我们 RUN 12 的 `Application memory is inaccessible or reserved by IPC` 就是踩了这个坑）。
- acquire 侧 hasProvenCleanup 增加 `!failureSummary(report).retainResources` 门（cleanup-gated retries）。
- **回植范围**：wave-history.cjs 全量 verbatim；probe-reserved-gap.cjs 六处；acquire.cjs 两处错误消息拼接。**未回植**：acquire 的 hasProvenCleanup 门（slapah 无 supervisor/report 结构，需要结构移植，列为后续）。

### f47ddb6f（13:13Z）"Add explicitly confirmed experimental SD acquisition profile" —— ⭕ 未移植（备胎）
- 把 reserved-gap 竞态从 save 服务切到 SD 卡存储服务：acquisition-profile.cjs `PROFILES internal{expectedBytes:13616}/sd{14992, experimental, confirmed}`；环境变量 `NS2_ACQUISITION_PROFILE` + `NS2_EXPERIMENTAL_SD_CONFIRMED=1` + 交互 y；assertAllocationCost 取代硬编码 13616 检查；releasePin 增加 pin 句柄所有权检查；pinCost/pinWindow 移到 wave row 创建处。
- **无任何硬件验证**，作者标注 experimental。对我们的意义：slapah 的等价物是 `target.civ7.json` 的 pinningAllocationBytes（Civ7=6960）+ save 服务 objectId 0x87；换 SD 需要拿到 SD 存储服务的 objectId 并重新 tune pin 尺寸。当作「如果 Civ7 对 save 服务的后台干扰无法压制」的换目标方案。

### 9a9def30（08:54Z）"Automatically detect ExeFS content storage through NCM" —— 📝 记录
- dump-game 的 ExeFS 存储位置改由 NCM 自动探测（不再写死）。

### dd54ab57（08:15Z）"Clarify recovery after an interrupted game dump" —— 📝 记录
- 文档：dump 中断后的恢复步骤说明。

### 52c86c82（08:13Z）"Add read-only ExeFS and RomFS game export command" —— 📝 记录（3/4 后用）
- game-dump.cjs（宿主侧 177 行）：流式导出 + dump.json manifest + files.jsonl journal + progress.json + .partials 临时件（UUID 名）+ CHUNK_SIZE 0x40000 + 每文件 sha256 + checkedName 路径校验 + 5 秒快照节流。
- 依赖注入客户端（engine/lib/game-dump-client.cjs + 控制台 dump-game.cjs）提供只读 openFile/readFile。**前提是 memory-control session 已就绪**（我们目前死在 serve 入口之前），3/4 通过后再启用。

### 206a4f01（07:13Z）"Integrate savekit support, cleanup-gated retries and worker diagnostics" —— 📝 已知
- savekit 集成 + cleanup-gated retries + worker diagnostics 的基线提交（e3309c3/f47ddb6 在其上迭代）。

## 与 slapah 的差异结论
- x43 引擎与 slapah 同源（kurumuz 主干），但 x43 面向 SmileBASIC 入口（13616 调校），slapah 面向 Civ7（6960 调校）。
- 今日回植的 e3309c3 是「纯宿主侧诊断与批次账本」改动，与入口无关，安全。
- f47ddb6 的 SD profile 是唯一改变竞态目标的尝试，未验证，仅备胎。
- x43 未解决 native-batch hang（与我们同病），说明该 hang 是主干级未决问题。
