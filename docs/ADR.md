# Architecture Decision Record — Melody Snake

Date: 2026-10-22
Status: Accepted (Phase 0)

## Context

用户（民谣指弹自学者）需要一个本地工具：持续分析电脑播放的歌曲，把旋律拆成按时间顺序的音符轨迹，显示相邻音程与首调唱名，帮助建立「听觉 → 音程 → 唱名 → 吉他指板」的连接。

核心约束（来自工程规格书）：
- 本地运行、不上传音频、不依赖云端 API。
- 已确认音符不可被新输入覆盖；历史只能由用户显式修正。
- 不把每一帧音高估计当成一个音符（必须有时序切分）。
- 音高识别与唱名映射分离。
- 必须可测试、可验证，禁止用随机数/假数据冒充真实功能。

## 环境审计结果（Phase 0）

| 项 | 结果 |
|----|------|
| OS | Windows 11 (build 26200) |
| Node | v24.15.0 |
| npm | 11.12.1 |
| git | 2.53.0 |
| Python | anaconda3 Python 3.13.9（默认 `python`）；`py` 另有 3.14 / 3.13 / 3.11 |
| D 盘 | 可写，项目建于 `D:\melody-snake` |
| numpy | 已装（anaconda base） |
| sounddevice / soundcard / aubio / fastapi / websockets | **未装**（需在项目 venv 中安装） |

## 决策 1：双运行时架构（Python 音频引擎 + TypeScript 核心/UI）

**选定方案**：Python 负责「音频采集 + 音高估计」，TypeScript（React + Vite）负责「音符切分、轨迹、音程、唱名、UI」。

```
Python (backend)                          TypeScript (frontend)
───────────────                           ─────────────────────
WASAPI loopback / mic / file  ──PCM──►    (WebSocket: PitchEstimate)
YIN 音高估计                   ──帧──►    NoteEventDetector 状态机
                                          MelodyTrackStore（不可覆盖历史）
                                          IntervalCalculator / SolfegeMapper
                                          React UI（4 区）
```

**理由**：
1. Windows 系统音频捕获（WASAPI Loopback）在 Python 生态最可靠（`sounddevice` 基于 PortAudio，有官方 loopback 配方与预编译 wheel），在纯 Electron/Node 中需要编译原生模块（node-gyp + VS Build Tools），风险高、不可复现。
2. 基频估计是 DSP 密集计算，Python + numpy 成熟且可测（YIN 自实现，无外部依赖）。
3. 轨迹/音程/唱名/编辑/撤销是纯逻辑，且必须面向 UI，放 TypeScript 单一数据源，用 Vitest 测合成序列——精确对应规格书 Phase 1「不依赖音频」。
4. 切分状态机放 TS，与「不可覆盖历史」在同一处，保证历史不可被静默改写。

**代价与缓解**：双进程/双测试框架。缓解：WebSocket 协议是唯一跨语言契约（用 JSON 固定，见 README）；两套测试各自独立，跨语言集成测试用「Python 生成合成音频 → YIN → 音高帧 JSON fixture → TS 全流水线断言」。

## 决策 2：第一版不采用 Electron，用浏览器承载 UI

规格书把 Electron 列为「建议」，但允许「音频算法用 Python 经稳定接口独立运行」并强调「最简单可靠的实现」。浏览器 UI 本地运行同样满足「桌面本地」，且 Playwright 天然可测。Electron 可作为后续薄壳（只加载 URL），不改动核心。**当前不声称是 Electron 桌面应用。**

## 决策 3：基频算法选 YIN（自实现，numpy）

对比：
- **YIN**：确定性、无外部依赖、可解释、易测；对单音/近单旋律足够。**选定**。
- **pYIN**：概率化、需要训练/参数更多，首版收益低、复杂度高。
- **MPM**：对复音鲁棒性略好，但复音/多声源分离首版明确不做。

已知限制（如实记录）：单一基频适合单音/近单旋律；完整歌曲是多声源混合，不能假定基频一定对应人声主旋律。首版只承诺「单音或近似单旋律」。

## 决策 4：项目级 Python venv，不动全局环境

在 `D:\melody-snake\.venv` 建 venv，安装 `numpy pyaudiowpatch fastapi uvicorn pytest`（+ 测试用 `httpx` `websockets`）。不污染 anaconda 全局（CLAUDE.md 规则：环境确定，尽量不改本地环境）。

> 实测修正：pypi.org 在当前网络不可达（SSL 被重置），pip 需走清华镜像
> `-i https://pypi.tuna.tsinghua.edu.cn/simple`。

## 决策 6：WASAPI Loopback 用 pyaudiowpatch（非 sounddevice）

实测 sounddevice 0.5.6 的 `WasapiSettings` 无 loopback 参数，高层 API 不含 loopback。改用 **pyaudiowpatch**（PyAudio 分支，专为 WASAPI loopback 设计，自带 PortAudio 预编译 wheel）：
- `get_default_wasapi_loopback()` → 默认系统播放设备（本机 Realtek Audio，48kHz 立体声）。
- 已实测：默认 loopback 设备打开并读到真实音频，经服务器 `/ws` 持续产出音高帧。

## 决策 5：数据流契约

WebSocket 消息类型（Python → TS）：
- `pitch`：`PitchEstimate`（timestamp / frequencyHz / continuousMidi / roundedMidi / confidence / voiced / algorithm / diagnostics）
- `status`：采集与分析状态（sampleRate、clipping、silence、error）
- `session`：session 开始/暂停/恢复/结束

TS 侧产出：`NoteEvent`、`IntervalEvent`、`MelodyTrack`（见 frontend/src/core/types.ts）。

## 明确不做（首版）

- 完整歌曲多声源/主旋律分离（后续独立能力）。
- Electron 桌面壳（后续薄壳）。
- 云上传 / 云端 API / 大模型逐音符判断。

## 阶段计划（对应规格书 Phase 0–5）

见 `docs/plans/2026-10-22-melody-snake.md`。
