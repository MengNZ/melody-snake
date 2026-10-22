# 第三阶段研究记录：预训练模型选型（v3 规格书）

日期：2026-10-23

## 一、候选模型研究结论（读了代码，非只看 README）

| 候选 | 用途 | 许可证 | 权重位置 | 结论 |
|------|------|--------|----------|------|
| ROSVOT | 歌声→音符事件（音高+起止），抗伴奏 | MIT | **Google Drive**（唯一来源，无 HF 镜像/无 GitHub Release） | 最理想，但权重被墙 |
| UVR/BS-RoFormer | 人声分离 | GPL-3.0 | HuggingFace（可达） | 可用，但 GPL |
| RMVPE | 基频曲线 | 随 ROSVOT 打包 | 随 ROSVOT 被墙 | 辅助工具，暂缓 |
| STARS | 歌词/音素 | 未深究 | — | 暂缓（可选） |

ROSVOT 代码结构：NATSpeech/DiffSinger 风格框架，推理入口 `inference/rosvot.py`，输入 WAV → MelNet(mel) + RMVPE(f0) + WordbdExtractor(词边界) + MidiExtractor(音符)，输出 `note_pred`(音高) + `note_itv_pred_secs`(起止秒)，**可直接映射到现有 NoteEvent**。依赖：torch + librosa + pyworld + pretty_midi + pyyaml。

## 二、关键阻塞（已实测）

1. **ROSVOT 权重只在 Google Drive**，实测 `http=000`（被墙）；HuggingFace 无镜像、GitHub 无 Release。
2. **用户梯子（Clash 7890）多节点对 Google 系全不通**（google/drive/youtube=000），但能通 HuggingFace（200）。判断为节点 IP 被 Google 拉黑或规则分流。

## 三、选型决策：路线 B 用 demucs（非 BS-RoFormer）

理由：
- **许可证更干净**：demucs = MIT；BS-RoFormer = GPL-3.0（对用户未来产品是隐患）。
- **安装不动环境**：demucs 只装 4 个小包，复用 d2l 的 torch 2.6，不升级 numpy/scipy（audio-separator 会把 numpy 1.26→2.2、scipy 1.11→1.15，故弃用）。
- 权重从 Meta CDN（dl.fbaipublicfiles.com）直下成功，80MB，不需梯子。
- CLI 简单：`demucs --two-stems=vocals`。

## 四、GPU 环境问题（重要，需用户决策）

**RTX 5070 是 Blackwell(sm_120)，但 d2l 的 torch 2.6.0+cu124 不支持它**，实测 CUDA 报 `no kernel image is available for execution on the device`。需要 torch 2.7+/cu128 才能用 GPU。

当前 CPU 推理速度：demucs 约 2.7 倍实时（30s 片段 ≈ 15s），对最小验证够用。是否需要升级 torch 到 cu128（改动 d2l 环境、约 2.5GB 下载）由用户决定。

## 五、已就绪的最小验证工具

- `backend/benchmark/route_b.py`：`mix → demucs(人声分离) → YIN → 切分 → 音符`，已端到端跑通。
- 运行：`python -m benchmark.route_b --wav song.wav [--ref song.ref.json] --out-dir out`。

## 六、下一步（待办）

- **缺真实歌曲片段**（20-30 秒、主唱清晰的普通话流行歌）。用户提供后跑最小验证。
- 真实素材到位前，不宣称核心识别问题已解决。
