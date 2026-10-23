"""System-audio transcription flow (route B, offline).

record_loopback -> Demucs vocal separation -> RMVPE (or YIN fallback) -> note events.

The separation runs in the d2l_py310 env (torch + demucs). Note extraction
reuses this project's pitch estimators and TypeScript segmentation CLI.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

from .audio.loopback_source import LoopbackSource
from .engine import process_audio

# CUDA-capable env (torch + demucs). CPU is used because torch 2.6+cu124 cannot
# run kernels on the RTX 5070 (Blackwell sm_120); see docs/phase3-research.md.
D2L_PY = "D:/Users/Ms/anaconda3/envs/d2l_py310/python.exe"

# Bundled TS segmentation CLI (reuses the exact app segmentation).
_SEGMENT_CLI = Path(__file__).resolve().parents[2] / "frontend" / "scripts" / "dist" / "segment-cli.mjs"


def record_loopback(duration_seconds, output_wav, device_index=None, block_size=2048):
    """Capture `duration_seconds` of system playback audio into a mono 16-bit WAV."""
    src = LoopbackSource(device_index=device_index, block_size=block_size)
    src.open()
    sr = src.sample_rate
    chunks = []
    total = 0
    target = int(duration_seconds * sr)
    try:
        while total < target:
            block = src.read(block_size)
            if block is None:
                break
            chunks.append(block.samples)
            total += len(block.samples)
    finally:
        src.close()

    samples = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(output_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return str(output_wav), sr


def separate_vocals(mix_path, out_dir, device="cpu"):
    subprocess.run(
        [D2L_PY, "-m", "demucs.separate", "--two-stems=vocals",
         "--shifts", "0",  # deterministic: disable random test-time shifts
         str(mix_path), "-o", str(out_dir), "-d", device],
        check=True,
        capture_output=True,
    )
    vocals = Path(out_dir) / "htdemucs" / Path(mix_path).stem / "vocals.wav"
    if not vocals.exists():
        raise FileNotFoundError(f"expected separated vocals at {vocals}")
    return vocals


RMVPE_SEGMENTATION_CONFIG = {
    "candidateConfirmFrames": 9,
    "minNoteDurationMs": 120,
    # RMVPE's stable F0 supports tighter boundaries. At 0.7, semitone-spaced
    # pitches during slow slides drifted with the rolling median and merged.
    # 0.30 also preserves the short C# in the user's target-song capture.
    "pitchToleranceSemitones": 0.30,
    "transitionStabilitySemitones": 0.35,
}


def extract_notes(audio_path, frames_out=None, pitch_method="yin", confidence_threshold=0.6,
                  segmentation_config=None):
    """WAV -> selected pitch estimator -> the app's TS note segmentation."""
    from .audio.file_source import read_wav_mono

    samples, sr = read_wav_mono(str(audio_path))
    if pitch_method == "yin":
        frames = process_audio(samples, sr)
    elif pitch_method == "rmvpe":
        from .pitch.rmvpe import process_audio_rmvpe
        frames = process_audio_rmvpe(samples, sr, min_confidence=confidence_threshold)
    else:
        raise ValueError(f"unknown pitch method: {pitch_method}")

    if not _SEGMENT_CLI.exists():
        raise FileNotFoundError(
            f"segment CLI not built at {_SEGMENT_CLI}; run `cd frontend && node scripts/build-segment-cli.mjs`"
        )

    with tempfile.TemporaryDirectory() as td:
        frames_path = os.path.join(td, "frames.json")
        notes_path = os.path.join(td, "notes.json")
        config_path = os.path.join(td, "segmentation.json")
        with open(frames_path, "w", encoding="utf-8") as f:
            json.dump(frames, f)
        command = ["node", str(_SEGMENT_CLI), frames_path, notes_path]
        if segmentation_config:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(segmentation_config, f)
            command.append(config_path)
        proc = subprocess.run(
            command,
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"segment-cli failed: {proc.stderr}")
        with open(notes_path, encoding="utf-8") as f:
            notes = json.load(f)
        if frames_out is not None:
            with open(frames_out, "w", encoding="utf-8") as f:
                json.dump(frames, f)
    return notes, sr


def record_and_transcribe(duration_seconds, device="cpu", out_dir=None, pitch_method="auto"):
    """Record a mix, separate vocals, estimate F0, and return note events.

    Saves all artifacts under `out_dir` (default: project `recordings/<timestamp>/`):
      recorded_mix.wav, vocals.wav, pitch_frames.json, notes.json, run_info.json

    `auto` uses Demucs + RMVPE when the local ONNX model exists; otherwise it
    preserves the previous Demucs + YIN path. Explicit `rmvpe` fails clearly if
    model weights are missing.
    """
    if out_dir is None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        out = Path(__file__).resolve().parents[2] / "recordings" / stamp
    else:
        out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    mix = out / "recorded_mix.wav"
    mix_path, _ = record_loopback(duration_seconds, mix)
    return transcribe_audio_file(mix_path, out_dir=out, device=device,
                                 pitch_method=pitch_method, copy_mix=False,
                                 input_kind="system")


def transcribe_audio_file(audio_path, out_dir=None, device="cpu", pitch_method="auto",
                          copy_mix=True, input_kind="file"):
    """Analyze a WAV through the same offline separation, F0, and app segmenter.

    The output directory retains the input (unless it already lives at the
    canonical path), vocal stem, pitch frames, notes, and run metadata.
    """
    audio_path = Path(audio_path)
    if out_dir is None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        out = Path(__file__).resolve().parents[2] / "recordings" / stamp
    else:
        out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if pitch_method == "auto":
        from .pitch.rmvpe import default_model_path
        pitch_method = "rmvpe" if default_model_path().is_file() else "demucs_yin"
    if pitch_method not in {"rmvpe", "demucs_yin"}:
        raise ValueError("pitch_method must be 'auto', 'rmvpe', or 'demucs_yin'")
    if pitch_method == "rmvpe":
        from .pitch.rmvpe import default_model_path
        if not default_model_path().is_file():
            raise FileNotFoundError(
                f"RMVPE weights are missing at {default_model_path()}; "
                "run `python -m benchmark.download_rmvpe_model` first"
            )

    mix = out / "recorded_mix.wav"
    if copy_mix and audio_path.resolve() != mix.resolve():
        shutil.copyfile(audio_path, mix)
    else:
        mix = audio_path
    with wave.open(str(mix), "rb") as wav:
        sr = wav.getframerate()
        duration_seconds = wav.getnframes() / sr
    vocals = separate_vocals(mix, out, device=device)
    estimator = "rmvpe" if pitch_method == "rmvpe" else "yin"
    segmentation = RMVPE_SEGMENTATION_CONFIG if estimator == "rmvpe" else None
    notes, sr2 = extract_notes(
        vocals, frames_out=out / "pitch_frames.json", pitch_method=estimator,
        confidence_threshold=0.6, segmentation_config=segmentation,
    )

    (out / "notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    run_info = {
        "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": round(duration_seconds, 3),
        "device": device,
        "recorded_mix": str(mix),
        "vocals": str(vocals),
        "recorded_sample_rate": sr,
        "note_sample_rate": sr2,
        "n_notes": len(notes),
        "pitch_method": pitch_method,
        "input_kind": input_kind,
        "confidence_threshold": 0.6 if estimator == "rmvpe" else None,
        "segmentation_config": segmentation,
    }
    (out / "run_info.json").write_text(json.dumps(run_info, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "recorded_mix": str(mix),
        "vocals": str(vocals),
        "sample_rate": sr2,
        "notes": notes,
        "out_dir": str(out),
        "pitch_method": pitch_method,
    }
