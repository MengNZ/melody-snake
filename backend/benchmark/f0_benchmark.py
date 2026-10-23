"""Run project YIN and score frame-level pitch against a 2-column time/F0 CSV."""
import argparse
import csv
import json
from pathlib import Path

from melody_snake.audio.file_source import read_wav_mono
from melody_snake.engine import DEFAULT_FRAME_SIZE, process_audio
from benchmark.f0_metrics import evaluate_f0


def read_reference(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            try:
                t, hz = float(row[0]), float(row[1])
            except ValueError:
                continue  # header
            rows.append({"time": t, "f0_hz": hz})
    if not rows:
        raise ValueError(f"no numeric time/F0 rows found in {path}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--ref-csv", required=True, help="CSV columns: time_seconds,f0_hz; 0 Hz means unvoiced")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-time-delta", type=float, default=0.012)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    samples, sr = read_wav_mono(args.wav)
    frames = process_audio(samples, sr)
    ref = read_reference(args.ref_csv)
    center_offset = DEFAULT_FRAME_SIZE / (2 * sr)
    metrics = evaluate_f0(ref, frames, max_time_delta_s=args.max_time_delta,
                          prediction_time_offset_s=center_offset)
    (out / "yin_frames.json").write_text(json.dumps(frames, indent=2), encoding="utf-8")
    (out / "f0_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
