# Melody Snake 第三阶段报告：核心识别能力验证与改造（v3）

> 依据 `工程prompt-v3.md` 执行。所有结论均来自实际运行；未完成/未验证的已明确标注，**不宣称未经真实歌曲验证的能力**。

---

## 一、技术诊断：为什么旧算法（YIN）无法处理完整混音

YIN 是**单一基频估计**，每个时间窗只返回一个频率。完整流行歌曲里同时存在主唱、贝斯（低频）、和弦垫、鼓（宽带噪声），YIN 会追踪能量最强的成分——通常是贝斯或和弦，而不是主唱旋律。

- 这已经在第二阶段实证：合成混音样本 `E_mix`（旋律+和弦+贝斯+鼓）的 precision = recall = **0**。
- 结论：**这是方法上限，不是调阈值能解决的**。单一 f0 估计不适用于多声源混合信号，必须换成分离+转录或端到端 AST 模型。

---

## 二、候选模型研究（读了代码与权重来源，非只看 README）

| 候选 | 用途 | 许可证 | 权重位置 | 结论 |
|------|------|--------|----------|------|
| **ROSVOT** | 歌声→音符事件（音高+起止），抗伴奏 | MIT | **Google Drive**（唯一来源） | 最理想；权重被墙，无法下载 |
| UVR / BS-RoFormer | 人声分离 | GPL-3.0 | HuggingFace（可达） | 可用但 GPL |
| RMVPE | 基频曲线（辅助） | 随 ROSVOT 打包 | 随 ROSVOT 被墙 | 暂缓 |
| STARS | 歌词/音素（可选） | 未深究 | — | 暂缓 |

ROSVOT 代码结构已核实（`inference/rosvot.py`）：输入 WAV → MelNet(mel) + RMVPE(f0) + WordbdExtractor(词边界) + MidiExtractor(音符)，输出 `note_pred`(音高) + `note_itv_pred_secs`(起止秒)，**可直接映射到现有 NoteEvent**。依赖 torch + librosa + pyworld + pretty_midi + pyyaml。

---

## 三、方案对照 A vs B（诚实：真实音频对照未完成）

| 路线 | 状态 | 原因 |
|------|------|------|
| **A. 原始混音 → ROSVOT** | ❌ **阻塞，未运行** | 权重仅在 Google Drive，实测 `http=000`（被墙）；用户 Clash 多个节点对 google/drive/youtube 全不通（对 huggingface 能通 200）；HuggingFace 无镜像、GitHub 无 Release |
| **B. 混音 → 人声分离 → 音符** | ✅ 已搭建，机械验证通过 | 分离用 demucs（见选型），音符用现有 YIN+切分 |

**规格书要求的「A/B 真实音频对照」未能完成**，因为 A 的权重无法获取。这是当前最大的未完成项，不隐瞒。

---

## 四、选型理由

1. **分离模型选 demucs 而非 BS-RoFormer**（对规格书候选的偏离，理由充分）：
   - 许可证：demucs = **MIT**；BS-RoFormer = GPL-3.0（对用户未来产品是传染性许可隐患）。
   - 安装：demucs 只装 4 个小包、复用已有 torch，**不动 numpy/scipy**；audio-separator 会把 numpy 1.26→2.2、scipy 1.11→1.15，污染用户 DL 环境，故弃用。
   - 权重：demucs 从 Meta CDN 直下成功（80MB，无需梯子）；BS-RoFormer 是 `.ckpt` 需额外模型代码。
2. **采用「分离 → 现有 YIN+切分」而非端到端 AST**：因 ROSVOT 权重不可得，退而求其次；分离后的人声接近单音，正好落在我第二阶段已验证 f1=1.00 的 YIN+切分能力范围内。
3. 完整保留规格书要求的既有结构（React/TS 前端、轨迹历史、音程、采集、WebSocket/FastAPI）。

---

## 五、改动文件清单与架构

**新增**：
- `backend/melody_snake/transcribe.py` — `record_loopback`(录系统音频) + demucs 分离 + YIN 切分 → 音符
- `backend/benchmark/route_b.py` — 本地 WAV 的实验入口（`mix → demucs → 音符`）
- `docs/phase3-research.md` / `docs/phase3-report.md`

**修改**：
- `backend/melody_snake/server.py` — 新增 `POST /analyze`（录制 N 秒系统音频 → 分离 → 返回音符）
- 前端 `useEngine.ts` / `ControlBar.tsx` / `App.tsx` / `styles.css` — 新增「分析系统音频」按钮 + 时长输入 + analyzing 状态
- `backend/benchmark/benchmark.py`、`frontend/scripts/build-segment-cli.mjs` — 切分 CLI 打包路径挪到 `scripts/dist/`（避免 vite build 清空 `dist/`）

**架构**（在既有双运行时之上加一层离线转录）：

```
系统音频(WASAPI loopback) ──录制N秒──► WAV ──demucs(CPU)──► 人声 ──YIN──► 切分(TS) ──► NoteEvent ──► 现有轨迹/音程/唱名/UI
```

---

## 六、测试结果与未解决问题

### 已机械验证（实际运行）
- demucs 分离：8 秒合成混音 → 分离出 `vocals.wav` / `no_vocals.wav`，CPU 约 2.7 倍实时速度。
- 录制系统音频：48kHz、时长准确；系统静音时振幅 0（无声音时正确）。
- `POST /analyze` 端点：录制→分离→出音符，返回 `ok=True`（静音 → 0 音符，正确）。
- UI 按钮：点击 → 「分析中…」→ 完成 → 复位，端到端跑通。

### 未解决 / 未验证（如实列出）
1. **真实歌曲旋律精度未测**：整条链路在真实普通话流行歌上的 precision/recall/八度错误率仍是**未知**——因为尚未拿到真实歌曲片段做实测。这是最关键的缺口。
2. **GPU 不可用**：RTX 5070 是 Blackwell(sm_120)，d2l 的 torch 2.6.0+cu124 不支持（实测 `no kernel image available`），需 torch 2.7+/cu128。当前 CPU 速度对 20-30 秒片段够用。
3. **路线 A（ROSVOT）权重被墙**：若后续能拿到权重（VPN 换可用节点 / 香港服务器），ROSVOT 仍是更优的端到端 MIT 方案。

---

## 七、Windows 本地运行步骤（含权重下载）

环境：项目 venv（`D:\melody-snake\.venv`）+ CUDA 环境 `d2l_py310`（torch + demucs，已装好）。

```bash
# demucs 权重已自动下载并缓存在 C:\Users\Ms\.cache\torch\hub（80MB，Meta CDN 直下）
# 打包切分 CLI（首次或改了切分代码后）
cd D:\melody-snake\frontend && node scripts/build-segment-cli.mjs && npm run build && cd ..

# 启动（一键）
D:\melody-snake\run.bat
# 或手动
cd D:\melody-snake\backend && ..\.venv\Scripts\python.exe -m melody_snake.main
```

首次使用无需额外下载（demucs 权重已就位）。若换机器，demucs 会重新从 Meta CDN 自动下权重。

---

## 八、操作说明

### 网易云系统音频（主流程）
1. 网易云播放一首**人声清楚**的歌。
2. 浏览器打开 `http://127.0.0.1:8000`。
3. 到有唱的段落点 **「分析系统音频 20s」**（时长可调 5~120 秒）。
4. 约 40 秒后，轨迹显示旋律音符（音名/唱名/音程/起止时间）。

### 本地音频（实验/评测）
```bash
cd D:\melody-snake\backend
..\.venv\Scripts\python.exe -m benchmark.route_b --wav D:\song.wav [--ref D:\song.ref.json] --out-dir D:\out
```

---

## 九、诚实声明

- **未经真实歌曲验证，不宣称核心识别问题已经解决。** 当前只证明了「系统音频 → 分离 → 音符」的机制跑通，真实人声上的旋律准确率仍是推测。
- A/B 对照因 ROSVOT 权重被墙而未完成，未用「只报 B 更好」来掩盖这一点。
- 下一步：拿到一段 20-30 秒、主唱清晰的普通话流行歌，实测路线 B 的旋律精度；若用户能解决 Google Drive 访问，再补路线 A 对照。
