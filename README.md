# Melody Snake（旋律贪吃蛇）

本地实时旋律识别工具：持续分析电脑正在播放的音频（或音频文件 / 麦克风），把旋律拆成按时间顺序的音符轨迹，显示相邻音程与首调唱名，帮助建立「听觉 → 音程 → 唱名 → 吉他指板」的连接。

**这不是调音器，也不是频率计。** 它的核心是生成一条可回溯、可修正、按时间顺序延伸的音符事件轨迹——已确认的音符不会被新输入覆盖。

---

## 一、当前真实能力（直接回答关键问题）

| 问题 | 结论 | 证据 |
|------|------|------|
| 能捕获 Windows 系统播放音频吗？ | ✅ 能 | WASAPI Loopback（pyaudiowpatch），实测打开 Realtek 设备读到真实音频并持续产出音高帧 |
| 能实时检测音高吗？ | ✅ 能 | 自实现 YIN，实测 440Hz/C4/低音/高音/静音/噪声 |
| 能把连续音高合并成稳定音符事件吗？ | ✅ 能 | 状态机 + 滞回，实测长音/短音/快音/滑音/颤音/重起音 |
| 历史音符会被新音符覆盖吗？ | ✅ 不会 | 不可变轨迹 store，只追加；修正必须显式操作并留痕 |
| 相邻音程经过测试吗？ | ✅ 是 | C4→E4=大三度、E4→D4=下行大二度、D4→G4=纯四度等 |
| 唱名按选定调性动态计算吗？ | ✅ 是 | C/E 大调 + 调外音升降标记，改调性不改原始音高 |
| 能可靠分离完整歌曲的主旋律吗？ | ❌ 不能 | 单一基频只适合单音/近单旋律；多声源分离明确未做 |

**首版只承诺「单音或近似单旋律」。** 完整歌曲是主唱 + 伴奏 + 贝斯 + 鼓的混合信号，单一基频估计不能假定一定对应人声主旋律。

---

## 二、架构

双运行时，WebSocket 是唯一跨语言契约：

```
Python (backend)                          TypeScript (frontend)
───────────────                           ─────────────────────
WASAPI loopback / 麦克风 / WAV 文件
        │ PCM (float32, mono)
        ▼
YIN 音高估计  ──PitchEstimate 帧──►  NoteEventDetector 状态机（音符切分）
        (WebSocket /ws)                 MelodyTrackStore（不可覆盖历史）
                                        IntervalCalculator（音程）
                                        SolfegeMapper（唱名）
                                        React UI（四区）
```

- **后端只做** 音频采集 + 音高估计（DSP 密集，Python + numpy 最可靠）。
- **前端只做** 切分、轨迹、音程、唱名、UI（纯逻辑，Vitest 测合成序列）。
- 音高识别与唱名映射**完全分离**；改调性只更新乐理解释，不改原始音高。

详细见 [`docs/ADR.md`](docs/ADR.md)。

---

## 三、目录结构

```
backend/melody_snake/
  theory/midi.py           频率 ↔ MIDI
  pitch/yin.py             YIN 基频估计（自实现，numpy）
  audio/source.py          AudioSource 抽象 + AudioBlock
  audio/file_source.py     WAV 文件输入
  audio/loopback_source.py WASAPI 系统音频捕获
  audio/mic_source.py      麦克风输入
  audio/devices.py         设备枚举
  engine.py                StreamingPitchProcessor + process_audio
  server.py                FastAPI + WebSocket（+ 托管构建后的前端）
  main.py                  入口
frontend/src/
  core/                    types / midi / interval / solfege / trackStore / segmentation / pipeline / exporter
  ws/client.ts             WebSocket 客户端
  state/useEngine.ts       React hook（连接后端与引擎）
  components/              ControlBar / MelodyTrack / MelodyNode / IntervalConnector / NoteInspector / DiagnosticsPanel
```

---

## 四、安装

前置：Node ≥ 18，Python ≥ 3.11（本机已用 anaconda Python 3.13）。

```bash
# 后端依赖（项目级 venv，不动全局；pypi 走清华镜像）
cd D:\melody-snake
python -m venv .venv
.venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r backend\requirements.txt

# 前端依赖
cd D:\melody-snake\frontend
npm install
```

> 若 `pypi.org` 直连报 SSL 错误，属网络问题，用上面的清华镜像即可。

---

## 五、运行

**一键（生产模式，推荐）**：双击 `D:\melody-snake\run.bat`
→ 自动构建前端、启动后端、打开浏览器 `http://127.0.0.1:8000`。

**手动**：

```bash
# 构建前端（产物在 frontend/dist，后端会托管它）
cd D:\melody-snake\frontend && npm run build

# 启动后端（同时服务 UI + WebSocket）
cd D:\melody-snake\backend && ..\.venv\Scripts\python.exe -m melody_snake.main
```

**开发模式**（前端热更新）：双击 `dev.bat`，前端 `:5173`，后端 `:8000`。

---

## 六、使用

界面分四区：

1. **顶部控制栏**：输入源（系统音频 / 麦克风 / 音频文件）、调性选择、当前音、开始 / 暂停 / 继续 / 停止 / 新建轨迹 / 导出 JSON / 导出 CSV。
2. **中央旋律轨迹**：确认的音符按时间顺序排列，节点之间连线显示音程（↑大三度 +4 等）；当前候选音以虚线节点区分，不会覆盖历史。
3. **右侧音符详情**：点击节点查看音名 / MIDI / 唱名 / 起止 / 置信度 / 前后音程，并可手动修正（输入音名如 `G4`）与撤销。
4. **底部诊断**：连接状态、采样率、切分状态、已确认音符数、当前置信度、错误信息。

**用音频文件快速验证**：选「音频文件」→ 填 WAV 路径（如 `D:\song.wav`）→ 开始。项目里已有测试旋律 `D:\melody-snake\test_melody.wav`（C4→E4→D4→G4）。

---

## 七、测试

```bash
# 前端（Vitest，44 个测试）
cd D:\melody-snake\frontend && npm test

# 前端类型检查 + 构建
cd D:\melody-snake\frontend && npm run build

# 后端（pytest，17 个测试，含 WebSocket 集成）
cd D:\melody-snake\backend && ..\.venv\Scripts\python.exe -m pytest -q
```

覆盖：MIDI/音名/八度转换、音程命名、唱名映射（含调外音）、轨迹不可覆盖 + 编辑 + 撤销、音符切分（长音/快音/滑音/颤音/重起音/静音/异常值）、YIN（正弦/静音/噪声/高低音）、文件→YIN→WebSocket→音符事件全流水线、导出解析。

详见 [`docs/test-report.md`](docs/test-report.md)。

---

## 八、算法说明

**基频估计（YIN）**：差异函数（FFT 加速的自相关 + 前缀和，精确计算）→ 累积均值归一化 → 绝对阈值 + 局部最小值步进 → 抛物线插值。置信度 = 1 − 非周期性（不是校准概率）。单一基频适合单音/近单旋律。

**音符切分（状态机）**：`IDLE → CANDIDATE → ACTIVE → TRANSITION`，用滚动中位数做稳健音高、音高容差 + 滞回吸收颤音/异常帧、静音间隙分音、最短时长过滤点击噪声。参数集中在 `DEFAULT_SEGMENTATION_CONFIG`，由测试确定。

**音程**：相邻**已确认音符**的 MIDI 差 → 方向 / 半音数 / 音程名（纯/大/小/增）/ 复音程位移。同音区分重复音。

**唱名**：调性音阶（大小调音程模式）→ 首调唱名（Do/Re/Mi/Fa/Sol/La/Si），调外音显示升降（如 `Fa♯`），不强制映射成自然音级。

---

## 九、数据模型（TypeScript 类型，后端 JSON 对齐）

`AudioFrame` → `PitchEstimate`（timestamp / frequencyHz / continuousMidi / roundedMidi / confidence / voiced / algorithm / diagnostics）→ `NoteEvent`（id / index / startTime / endTime / midiNote / noteName / confidence / status / source / originalMidiNote / correctionHistory）→ `IntervalEvent`（deltaSemitones / direction / intervalName / …）→ `MelodyTrack`（selectedKey / notes / …）。

WebSocket 消息：`{"type":"pitch", …PitchEstimate}` 与 `{"type":"status", state, sampleRate, source, error}`。

---

## 十、已知限制（如实记录）

1. **多声源分离未做**：完整歌曲的旋律提取不保证对应主旋律。
2. **文件输入仅支持 WAV**（8/16/32-bit PCM、32-bit float；24-bit 未支持）。MP3/FLAC 需后续加解码器（如 `soundfile`/`librosa` 或 ffmpeg）。
3. **八度误判可能**：某些泛音强的音色，YIN「首个低于阈值」可能选到倍频程；后续可加八度校正。
4. **系统音频实时模式下不保存原始音频**：因此「局部回放」未实现（浏览器无法播放没存下来的系统音频）；文件模式下后续可加片段循环。
5. **第一版非 Electron 桌面壳**：用浏览器承载本地 UI，Electron 可作后续薄壳，不改核心。

---

## 十一、下一阶段建议

1. 文件模式局部循环回放（后端托管 WAV，前端 `<audio>` 定位片段）。
2. 八度校正 + pYIN 化置信度校准。
3. MP3/FLAC 解码。
4. 多声源旋律分离（独立能力，不靠调阈值冒充）。
5. Electron 薄壳。
