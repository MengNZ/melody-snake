"""Run RMVPE ONNX against a time-aligned two-column time/F0 CSV reference.

The model returns an F0 for every frame, so this benchmark sweeps explicit
voicing-confidence thresholds and scores all predictions using the same
metrics as ``f0_benchmark``. The ONNX runtime is an optional dependency.
"""

import argparse
import csv
import json
from pathlib import Path

import soundfile as sf

from benchmark.f0_metrics import evaluate_f0
from rmvpe_onnx import RMVPE


def read_reference(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            try:
                t, hz = float(row[0]), float(row[1])
            except ValueError:
                continue
            rows.append({"time": t, "f0_hz": hz})
    if not rows:
        raise ValueError(f"no numeric time/F0 rows found in {path}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--ref-csv", required=True, help="CSV columns: time_seconds,f0_hz; 0 Hz means unvoiced")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--thresholds", default="0,0.01,0.03,0.05,0.1,0.2,0.4,0.6")
    ap.add_argument("--max-time-delta", type=float, default=0.012)
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    audio, sr = sf.read(args.wav, dtype="float32", always_2d=False)
    rmvpe = RMVPE(model_path=args.model, device="cpu")
    times, frequencies, confidences, _ = rmvpe.predict(audio, sr)
    raw = [
        {"timestamp": float(t), "frequencyHz": float(hz), "confidence": float(c)}
        for t, hz, c in zip(times, frequencies, confidences)
    ]
    (out / "rmvpe_raw_frames.json").write_text(json.dumps(raw), encoding="utf-8")

    reference = read_reference(args.ref_csv)
    thresholds = [float(x) for x in args.thresholds.split(",")]
    results = {}
    for threshold in thresholds:
        pred = [
            {"timestamp": x["timestamp"], "frequencyHz": x["frequencyHz"] if x["confidence"] >= threshold else None}
            for x in raw
        ]
        results[str(threshold)] = evaluate_f0(
            reference, pred, max_time_delta_s=args.max_time_delta,
            prediction_time_offset_s=0.0,
        )
    result = {
        "source": str(Path(args.wav)),
        "reference": str(Path(args.ref_csv)),
        "model": str(Path(args.model)),
        "model_frames": len(raw),
        "threshold_results": results,
        "selection_note": "Threshold selection on this track is exploratory; choose on validation tracks before reporting held-out performance.",
    }
    (out / "rmvpe_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
