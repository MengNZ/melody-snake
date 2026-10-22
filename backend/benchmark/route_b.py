"""Route B experiment: raw mix -> demucs vocal separation -> YIN -> note events.

Usage:
  python -m benchmark.route_b --wav song.wav [--ref song.ref.json] --out-dir out

The separation runs in the d2l_py310 env (has torch+demucs); the note extraction
reuses the existing YIN + segmentation pipeline from this project.
"""

import argparse
import json
import subprocess
from pathlib import Path

from .benchmark import DEFAULT_SEGMENT_CLI, run_pipeline
from .metrics import evaluate

# CUDA-capable env (torch + demucs). CPU is used because torch 2.6+cu124 cannot
# run kernels on the RTX 5070 (Blackwell sm_120); see the phase report.
D2L_PY = "D:/Users/Ms/anaconda3/envs/d2l_py310/python.exe"


def separate_vocals(mix_path, out_dir, device="cpu"):
    out = Path(out_dir)
    subprocess.run(
        [D2L_PY, "-m", "demucs.separate", "--two-stems=vocals",
         str(mix_path), "-o", str(out), "-d", device],
        check=True,
    )
    vocals = out / "htdemucs" / Path(mix_path).stem / "vocals.wav"
    if not vocals.exists():
        raise FileNotFoundError(f"expected separated vocals at {vocals}")
    return vocals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--ref", default="")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"[route B] separating vocals from {args.wav} (device={args.device}) ...")
    vocals = separate_vocals(args.wav, out, args.device)
    print(f"[route B] vocals -> {vocals}")

    print("[route B] extracting notes from vocals ...")
    notes, sr = run_pipeline(vocals, DEFAULT_SEGMENT_CLI)
    print(f"[route B] {len(notes)} notes @ {sr} Hz")

    result = {"source": str(args.wav), "vocals": str(vocals), "sample_rate": sr, "notes": notes}
    if args.ref:
        ref = json.loads(Path(args.ref).read_text(encoding="utf-8"))
        metrics = evaluate(notes, ref)
        result["metrics"] = metrics
        print(f"[route B] metrics: precision={metrics['note_precision']:.2f} "
              f"recall={metrics['note_recall']:.2f} octave={metrics['octave_errors']}")

    (out / "route_b_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[route B] result -> {out / 'route_b_result.json'}")


if __name__ == "__main__":
    main()
