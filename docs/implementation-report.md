# Melody Snake 实现报告书（第一版交付）

> 本文供第三方（ChatGPT）检验与决策下一步。所有结论均附可复现命令或验证记录；未验证的已明确标注，不把「读了代码」当作「验证过」。

- **代码仓库**：https://github.com/MengNZ/melody-snake （公开，分支 `main`）
- **本地路径**：`D:\melody-snake`
- **规格书**：`吉技/音感练习项目/工程prompt.md`
- **架构决策记录**：`docs/ADR.md`；**自检报告**：`docs/test-report.md`

---

## 0. 一句话结论

已实现并验证「音频输入 → 音高估计 → 音符切分 → 不可覆盖轨迹 → 音程 → 唱名 → 四区 UI」的完整可运行管线；**单音/近单旋律**场景下经合成音频 + 浏览器端到端验证通过。**完整歌曲多声源主旋律分离未做**（规格书允许的首版范围之外），并如实列出所有已知限制。

---

## 1. 真实能力对照（直接回答规格书「最终必须明确回答」的问题）

| 问题 | 结论 | 验证方式 |
|------|------|----------|
| 能捕获 Windows 系统播放音频？ | ✅ 能（机制已验） | WASAPI Loopback 打开 Realtek 设备（48kHz 立体声）、读到真实音频、经 `/ws` 持续产出音高帧 |
| 能实时检测音高？ | ✅ 能 | 自实现 YIN，正弦 440Hz/C4/E2/A5 误差 <3Hz，静音/白噪声判 unvoiced |
| 能把连续音高合并成稳定音符事件？ | ✅ 能 | 状态机+滞回，长音/快音/滑音/颤音/重起音/静音/异常值 8 类单测 |
| 历史音符会被覆盖？ | ✅ 不会 | 不可变轨迹 store，只追加；修正须显式操作并留 correctionHistory |
| 相邻音程经测试？ | ✅ 是 | 大三度/大二度/纯四度/纯五度/纯八度/同度 + 方向/复音程 |
| 唱名按调性动态计算？ | ✅ 是 | C/E 大调 + 调外音 `♯/♭` 标记，改调性不改原始音高 |
| 完整歌曲主旋律可靠分离？ | ❌ 不能 | 单一基频只适合单音/近单旋律，多声源分离明确未做 |
| 系统音频实时模式可局部回放？ | ❌ 未实现 | 实时模式不保存原始音频，无法回放 |

> 关键区分：系统音频捕获是「机制已验证」；**音高估计的精度只在合成单音/单旋律上验证过，未在真实混音歌曲上做过旋律级精度评估**。这点未夸大。

---

## 2. 架构与技术选型

双运行时，WebSocket 是唯一跨语言契约：

```
Python (backend)                          TypeScript (frontend)
───────────────                           ─────────────────────
WASAPI Loopback / 麦克风 / WAV 文件
        │ PCM float32 mono
        ▼
YIN 音高估计  ──PitchEstimate 帧──►  NoteEventDetector 状态机
        (WebSocket /ws)                MelodyTrackStore（不可覆盖）
                                       IntervalCalculator / SolfegeMapper
                                       React 四区 UI
```

- **后端**：Python 3.13（项目级 venv）。依赖 `numpy / pyaudiowpatch / fastapi / uvicorn`。
- **前端**：React 18 + TypeScript 5 + Vite 5 + Vitest 2。
- **职责边界**：后端只做「采集 + 音高估计」；前端只做「切分 + 轨迹 + 音程 + 唱名 + UI」。音高识别与唱名映射完全分离。

---

## 3. 与规格书的偏差（请重点评估，均已记录在 ADR）

1. **未用 Electron，用浏览器承载本地 UI**（ADR 决策2）。规格书把 Electron 列为「建议」，同时允许「音频算法用 Python 经稳定接口独立运行」并强调「最简单可靠的实现」。浏览器 UI 本地运行同样满足「桌面本地」，且 Playwright 天然可测。Electron 可作后续薄壳，不改核心。**当前不声称是 Electron 桌面应用。**
2. **WASAPI Loopback 用 `pyaudiowpatch` 而非 `sounddevice`**（ADR 决策6）。实测 sounddevice 0.5.6 的 `WasapiSettings` 无 loopback 参数、高层 API 不含 loopback，故改用专为 WASAPI loopback 设计的 PyAudio 分支（自带 PortAudio 预编译 wheel）。
3. **音符切分放在 TypeScript 而非 Python**。规格书允许「音频算法用 Python 经稳定接口独立运行」「不要强迫所有算法必须用 TypeScript」，其 Phase 1 把切分归入语言无关的「core」。我的划分：Python = 采集 + 音高估计；TS = 切分 + 轨迹 + 音程 + 唱名。理由：轨迹/编辑/撤销/不可覆盖与切分同处单一数据源，Vitest 可测合成序列。
4. **文件输入仅支持 WAV**（8/16/32-bit PCM、32-bit float；24-bit 不支持）。MP3/FLAC 需后续加解码器。
5. **未引入 ESLint**，以 `tsc --noEmit` 严格类型检查替代（规格书写「ESLint 或等价工具」）。

---

## 4. 验证证据（可复现）

### 4.1 自动化测试（全部通过）

```
# 前端 Vitest：44 通过 / 0 失败
cd D:\melody-snake\frontend && npm test
#   midi(7) interval(7) solfege(8) trackStore(9) segmentation(8) pipeline(3) exporter(2)

# 前端类型检查 + 生产构建：通过
cd D:\melody-snake\frontend && npm run build   # tsc --noEmit && vite build

# 后端 pytest：17 通过 / 0 失败
cd D:\melody-snake\backend && ..\.venv\Scripts\python.exe -m pytest -q
#   midi(5) yin(5) engine(4) server(3)
```

关键测试覆盖（对应规格书 7.1/7.2）：音高转换（A4=440、非法频率）、音程（C4→E4=大三度、C4→C5=纯八度等）、唱名（C/E 大调、调外音不强制）、事件切分（长音不重复、异常值不触发新音、快音不被吞、重起音分两事件、颤音/滑音不拆分、静音不误判）、不可覆盖轨迹 + 编辑 + 撤销、`C4→E4→D4→G4` 全流水线（顺序/时间戳单调/音程/历史保留）。

### 4.2 真实音频验证

| 测试集 | 结果 |
|--------|------|
| 440Hz / C4 / E2(82.4) / A5(880) 正弦 | 频率误差 <3Hz，置信度 >0.5 |
| 静音 / 白噪声 | unvoiced（f0=None） |
| 合成旋律 C4→E4→D4→G4（文件→YIN→WS→切分→轨迹→音程→唱名→UI） | 4 个音符 Do/Mi/Re/Sol，音程 ↑大三度+4、↓大二度−2、↑纯四度+5 |
| 系统 Loopback（Realtek，48kHz） | 打开读到真实音频、经 `/ws` 持续产出音高帧 |

### 4.3 UI 浏览器验证（Playwright，真实运行非静态截图）

- 应用启动、四区渲染、WebSocket 连接成功（「已连接」）。
- 文件模式端到端：选源→填路径→开始→轨迹出现 4 个确认音符，历史不被覆盖。
- 控制台 **0 错误**。

---

## 5. 开发过程中发现并修复的两个真实 bug

1. **YIN 周期系统性偏 2.7%**：绝对阈值在 CMNDF 的「下降斜率」上就触发，随后对斜率点做抛物线插值得到错误周期。修复：阈值触发后先步进到局部最小值，再做抛物线插值。
2. **快音符被吞**：切分状态机在 `commitNote()` 内重置了 transition 缓冲，而提交后又读该缓冲去播种下一个音符（已被清空），导致短音时长被算短、被最短时长规则丢弃。修复：提交前先拷贝 transition 缓冲。

（这两条说明：测试不是摆设，而是实际抓出了算法错误。）

---

## 6. 未完成 / 已知限制（如实列出）

1. **多声源旋律分离未做**（规格书明确列为「后续独立能力」，未用调阈值冒充）。
2. **八度误判风险**：YIN「首个低于阈值」对泛音强的音色可能选到倍频程，未加八度校正。
3. **文件输入仅 WAV**；24-bit WAV、MP3/FLAC 不支持。
4. **局部回放未实现**：实时模式不存原始音频；文件模式也未接 `<audio>` 片段循环。
5. **长期运行内存压力测试未做**。
6. **未做真实混音歌曲的旋律精度基准**（精确率/召回率未测）——这是「有效性」最需要补的证据。

---

## 7. 建议的下一步（供 ChatGPT 决策，非定论）

按「有效性补证据优先」排序：

1. **建立真实音频基准**：钢琴/吉他/人声单音 + 单旋律 + 带伴奏，测精确率/召回率，据此标定 YIN 阈值与切分参数（这是规格书 7.3 明确要求、目前最缺的一块）。
2. **八度校正**：对 YIN 候选做子谐波检查，降低倍频程误判。
3. **文件模式局部循环回放**（后端托管 WAV + 前端 `<audio>`）。
4. **MP3/FLAC 解码**（`soundfile`/`librosa` 或 ffmpeg）。
5. 之后再考虑多声源分离、Electron 薄壳。

---

## 8. 供检验的最小复现步骤

```bash
git clone https://github.com/MengNZ/melody-snake.git
cd melody-snake
python -m venv .venv
.venv/Scripts/python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r backend/requirements.txt
cd frontend && npm install && npm test && npm run build && cd ..
cd backend && ..\.venv\Scripts\python.exe -m pytest -q && cd ..
# 运行：见 README（run.bat 一键，或后端 -m melody_snake.main 后访问 127.0.0.1:8000）
```

> 注：`pypi.org` 直连在当前网络不可达（SSL 被重置），pip 需走清华镜像；系统音频捕获依赖 Windows WASAPI 设备，属平台能力。
