"""System-audio transcription flow (route B, offline).

record_loopback -> demucs vocal separation -> YIN -> note events.

The separation runs in the d2l_py310 env (torch + demucs); the note extraction
reuses this project's YIN + segmentation (via the bundled segment CLI).
"""

import json
import os
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
         str(mix_path), "-o", str(out_dir), "-d", device],
        check=True,
        capture_output=True,
    )
    vocals = Path(out_dir) / "htdemucs" / Path(mix_path).stem / "vocals.wav"
    if not vocals.exists():
        raise FileNotFoundError(f"expected separated vocals at {vocals}")
    return vocals


def extract_notes(vocals_path, frames_out=None):
    """vocals WAV -> YIN pitch frames -> TS segmentation -> note events."""
    from .audio.file_source import read_wav_mono

    samples, sr = read_wav_mono(str(vocals_path))
    frames = process_audio(samples, sr)

    if not _SEGMENT_CLI.exists():
        raise FileNotFoundError(
            f"segment CLI not built at {_SEGMENT_CLI}; run `cd frontend && node scripts/build-segment-cli.mjs`"
        )

    with tempfile.TemporaryDirectory() as td:
        frames_path = os.path.join(td, "frames.json")
        notes_path = os.path.join(td, "notes.json")
        with open(frames_path, "w", encoding="utf-8") as f:
            json.dump(frames, f)
        proc = subprocess.run(
            ["node", str(_SEGMENT_CLI), frames_path, notes_path],
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


def record_and_transcribe(duration_seconds, device="cpu", out_dir=None):
    """Full flow: record system audio, separate vocals, extract notes.

    Saves all artifacts under `out_dir` (default: project `recordings/<timestamp>/`):
      recorded_mix.wav, vocals.wav, pitch_frames.json, notes.json, run_info.json
    """
    if out_dir is None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        out = Path(__file__).resolve().parents[2] / "recordings" / stamp
    else:
        out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    mix = out / "recorded_mix.wav"

    mix_path, sr = record_loopback(duration_seconds, mix)
    vocals = separate_vocals(mix, out, device=device)
    notes, sr2 = extract_notes(vocals, frames_out=out / "pitch_frames.json")

    (out / "notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    run_info = {
        "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": duration_seconds,
        "device": device,
        "recorded_mix": str(mix),
        "vocals": str(vocals),
        "recorded_sample_rate": sr,
        "note_sample_rate": sr2,
        "n_notes": len(notes),
    }
    (out / "run_info.json").write_text(json.dumps(run_info, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "recorded_mix": str(mix),
        "vocals": str(vocals),
        "sample_rate": sr2,
        "notes": notes,
        "out_dir": str(out),
    }
