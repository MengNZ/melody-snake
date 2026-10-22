# Melody Snake 第二阶段报告：真实音频验证与算法修正

> 依据 `工程prompt-v2.md` 执行。所有数字均来自实际运行；未运行的已明确标注。

---

## 一、实际修改的文件与原因

### 修改（为修复基准中发现的问题）

| 文件 | 修改 | 原因 |
|------|------|------|
| `backend/melody_snake/engine.py` | `DEFAULT_FRAME_SIZE` 2048→1536，`DEFAULT_HOP` 512→256 | 46ms 窗把 80ms 快音符抹糊（干净段只剩 ~35ms），且 11.6ms 步进太粗。35ms 窗 + 5.8ms 步进提升时间分辨率，同时仍支持低至 60Hz |
| `frontend/src/core/segmentation.ts` | `minNoteDurationMs` 40→30 | 快音符被抹糊后时长被算短，40ms 门槛把它们当噪声丢弃 |
| 同上 | 新增 `transitionStabilitySemitones=0.3` | 快速滑音被切成 61/62/63 一串假音符；要求确认前音高稳定 |
| 同上 | 切分改用 `continuousMidi`（不再用 `roundedMidi`），仅在音符边界取整 | `roundedMidi` 把滑音量化成台阶，掩盖了「音高仍在移动」的事实 |

### 新增（基准工具）

- `backend/benchmark/synth.py` — 确定性合成（正弦/类钢琴/类吉他 Karplus-Strong/颤音/滑音）
- `backend/benchmark/metrics.py` — 音符匹配与指标（公式见下）
- `backend/benchmark/benchmark.py` — 编排器：WAV→YIN→切分 CLI→指标→JSON/CSV
- `backend/benchmark/generate_dataset.py` — 生成 9 个基准样本 + 真值
- `frontend/scripts/segment-cli.ts` + `build-segment-cli.mjs` — 把 TS 切分打包成可被 Python 调用的 CLI（复用同一份切分代码，非重实现）
- `backend/tests/test_benchmark.py`、`frontend/tests/segmentation.test.ts` — 回归测试

---

## 二、新增基准样本与真值来源

9 个样本，**真值全部来自合成参数，绝不用模型预测当真值**：

| 样本 | 内容 | 真值 |
|------|------|------|
| A_single_note | 440Hz 正弦 1s | C 大调 C4 一个音 |
| B_piano_melody | 类钢琴（1/n 谐波+衰减）C4-E4-D4-G4 | 合成器参数 |
| B_guitar_melody | 类吉他（Karplus-Strong）同上旋律 | 合成器参数 |
| C_fast_notes | 8 个 80ms 正弦连音（无间隔） | 合成器参数 |
| D_vibrato | 440Hz ±0.5 半音 5Hz 颤音 | 1 个音 |
| D_glissando | 按住 C4→滑到 E4→按住 E4 | 2 个音（滑音不标） |
| D_decay | 类钢琴 C4 衰减 1.5s | 1 个音 |
| D_repeat | C4、间隔、C4 | 2 个同音 |
| E_mix | 旋律+和弦垫+贝斯+打击乐 | 只标旋律 4 音 |

> 注意：B 是「合成的类钢琴/类吉他」，**不是真实录音**。真实录音与人工标注流程见第七节。

---

## 三、自动化测试结果（实际运行）

```
前端 Vitest：45 通过 / 0 失败    （新增快速滑音回归 1 个）
后端 pytest ：20 通过 / 0 失败    （新增全流水线回归 3 个）
```

基准（`benchmark_data/` 9 样本，全流水线）：

| 样本 | precision | recall | f1 | 音高准确率 | 八度错误 |
|------|-----------|--------|-----|-----------|----------|
| A_single_note | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| B_piano_melody | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| B_guitar_melody | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| C_fast_notes | 1.00 | **1.00** | 1.00 | 1.00 | 0 |
| D_vibrato | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| D_glissando | **1.00** | 1.00 | 1.00 | 1.00 | 0 |
| D_decay | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| D_repeat | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| E_mix | 0.00 | 0.00 | 0.00 | — | — |

**修复前 → 修复后**：C_fast_notes recall 0.38→1.00；D_glissando precision 0.67→1.00。

---

## 四、指标定义、结果与适用场景

匹配规则：按参考音符起始序贪心匹配，`时间重叠 / min(两音时长) ≥ 0.5` 视为时间匹配；再按音高差分类。

| 指标 | 公式 | 适用场景 |
|------|------|----------|
| 音符 precision | hits / n_predicted | 「报出来的音里有多少是对的」 |
| 音符 recall | hits / n_reference | 「该抓的音抓到了多少」 |
| F1 | 2PR/(P+R) | 综合 |
| 音高准确率 | hits / (hits+八度+错音高) | 时间对上了之后音高对不对 |
| 八度错误率 | octave / n_predicted | 倍频程误判 |
| 平均边界误差 | mean \|pred_onset − ref_onset\| | 起音对齐 |

其中 `hits` = 时间匹配且 \|音高差\| ≤ 0.5 半音；`八度` = 时间匹配且 11≤\|差\|≤13。

当前结果：合成单音/单旋律/快音/滑音/颤音/重复音全部 f1=1.00。这些指标**只在合成样本上验证过**，不适用于断言真实混音表现。

---

## 五、已发现但尚未解决的问题

1. **八度误判边界已量化但未修**：当第二谐波 ≥ 基频 5 倍时 YIN 会选到高八度（实测 1:5、1:10、1:20 都判错，1:2 正常）。真实乐器中基频通常不弱，但钢琴低音、部分管乐可能触发。**未加八度校正**——它可能引入新的低八度误判，需真实乐器数据验证后再决定。
2. **E_mix 完全失败**（precision/recall 0）：单一基频无法分离主旋律与伴奏，这是规格书明确划出的「多声源分离」范围外，不是调参能解决。
3. **无真实录音**：本阶段全部基准为合成音频；真实吉他/钢琴/完整歌曲仍缺，精确率/召回率在真实素材上的表现**仍是推测**。
4. 音高置信度未做概率校准（YIN 的 1−非周期性不是概率）。

---

## 六、如何在 Windows 电脑上复现

```bash
cd D:\melody-snake
# 1. 打包 TS 切分 CLI（基准依赖它）
cd frontend && node scripts/build-segment-cli.mjs && cd ..
# 2. 生成基准数据（9 个 WAV + 真值 JSON）
cd backend && ..\.venv\Scripts\python.exe -m benchmark.generate_dataset D:\melody-snake\benchmark_data
# 3. 跑基准，输出 metrics.json + summary.csv
..\.venv\Scripts\python.exe -m benchmark.benchmark --dataset D:\melody-snake\benchmark_data --out-dir D:\melody-snake\benchmark_results
# 4. 回归测试
..\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend && npm test
```

---

## 七、缺少真实录音时的最小自录+标注流程

我无法凭空生成真实吉他/钢琴/完整歌曲，因此提供以下最小流程（约 10 分钟）：

1. **录单音**：手机/电脑麦对准吉他，弹单个音（如空弦 E2、A2、D3、G3、B3、E4），每个 1 秒，间隔 1 秒，录成 WAV（可用 Audacity 导出 16-bit PCM WAV）。
2. **录单旋律**：弹一条你确定的旋律（比如《小星星》前两句），节奏稳定。
3. **录快音**：同一音快速反复 8 次，或快速音阶跑动。
4. **录完整片段**：录一段带伴奏的歌（作为压力测试，不指望通过）。
5. **标注**：新建与 WAV 同名的 `.ref.json`，内容为音符数组：
   ```json
   [{"midi": 40, "start": 0.0, "end": 1.0}, {"midi": 45, "start": 2.0, "end": 3.0}]
   ```
   起始/结束秒数和音名按你听感写（用调音器或 DAW 网格辅助确认音名）。
6. 把 WAV+ref.json 放进 `benchmark_data/`，重跑第六节第 3 步。

**你只要能给我这些文件，我就能跑出真实素材上的精确率/召回率，并据此决定是否加八度校正。**

---

## 八、哪些是实跑验证的、哪些仍是推测

**实跑验证**：
- 合成单音/单旋律（类钢琴/类吉他）/快音/滑音/颤音/衰减/重复音：f1=1.00。
- 快音修复、滑音修复、回归测试、八度误判边界（1:5 起）。

**仍是推测（未实跑）**：
- 真实吉他/钢琴/完整歌曲上的精度（缺素材）。
- 真实混音中主旋律是否会被伴奏抢走（E_mix 合成样本表明「会」，但真实歌未测）。
- 长期运行内存稳定性（未做压力测试）。
