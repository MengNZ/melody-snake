"""Feed RMVPE F0 into the app's NoteEventDetector and compare note events.

The MedleyDB melody reference is continuous F0, not score-level note events.
This benchmark derives note labels by MIDI rounding, a five-frame median
filter, and a 40 ms minimum reference run; those rules are recorded in output.
"""

import argparse
import csv
import json
import os
import subprocess
import tempfile
from pathlib import Path

from benchmark.metrics import evaluate

DEFAULT_SEGMENT_CLI = Path(__file__).resolve().parents[2] / "frontend" / "scripts" / "dist" / "segment-cli.mjs"


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
            midi = round(69 + 12 * __import__("math").log2(hz / 440)) if hz > 0 else None
            rows.append((t, midi))
    if not rows:
        raise ValueError(f"no numeric time/F0 rows found in {path}")
    return rows


def derive_reference_notes(rows, min_duration_s=0.04, median_width=5):
    labels = [pitch for _, pitch in rows]
    half = median_width // 2
    filtered = []
    for i in range(len(labels)):
        window = [p for p in labels[max(0, i - half):min(len(labels), i + half + 1)] if p is not None]
        if len(window) < (median_width // 2 + 1):
            filtered.append(None)
        else:
            window.sort()
            filtered.append(window[len(window) // 2])

    runs = []
    start = 0
    for i in range(1, len(filtered) + 1):
        if i == len(filtered) or filtered[i] != filtered[start]:
            pitch = filtered[start]
            if pitch is not None:
                t0 = rows[start][0]
                t1 = rows[i - 1][0]
                if t1 - t0 >= min_duration_s:
                    runs.append({"midi": pitch, "start": t0, "end": t1})
            start = i
    return runs


def run_segmenter(frames, segment_cli, config=None):
    with tempfile.TemporaryDirectory() as td:
        frames_path = os.path.join(td, "frames.json")
        notes_path = os.path.join(td, "notes.json")
        config_path = os.path.join(td, "config.json")
        Path(frames_path).write_text(json.dumps(frames), encoding="utf-8")
        command = ["node", str(segment_cli), frames_path, notes_path]
        if config is not None:
            Path(config_path).write_text(json.dumps(config), encoding="utf-8")
            command.append(config_path)
        proc = subprocess.run(command, capture_output=True, text=True)
        if proc.returncode:
            raise RuntimeError(f"segment-cli failed: {proc.stderr}")
        return json.loads(Path(notes_path).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-frames", required=True)
    ap.add_argument("--ref-csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--thresholds", default="0.2,0.4,0.6")
    ap.add_argument("--reference-median-width", type=int, default=5)
    ap.add_argument("--reference-min-duration", type=float, default=0.04)
    ap.add_argument("--config-json", default="{}", help="JSON overrides for the project NoteEventDetector")
    ap.add_argument("--sweep-configs", action="store_true", help="compare conservative segmentation settings")
    ap.add_argument("--start-time", type=float, default=None, help="limit evaluation to this inclusive time")
    ap.add_argument("--end-time", type=float, default=None, help="limit evaluation to this exclusive time")
    ap.add_argument("--segment-cli", default=str(DEFAULT_SEGMENT_CLI))
    args = ap.parse_args()

    raw = json.loads(Path(args.raw_frames).read_text(encoding="utf-8"))
    ref_rows = read_reference(args.ref_csv)
    if args.start_time is not None:
        raw = [x for x in raw if x["timestamp"] >= args.start_time]
        ref_rows = [x for x in ref_rows if x[0] >= args.start_time]
    if args.end_time is not None:
        raw = [x for x in raw if x["timestamp"] < args.end_time]
        ref_rows = [x for x in ref_rows if x[0] < args.end_time]
    ref_notes = derive_reference_notes(
        ref_rows, min_duration_s=args.reference_min_duration,
        median_width=args.reference_median_width,
    )
    results = {}
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    configs = {"current": json.loads(args.config_json)}
    if args.sweep_configs:
        configs = {
            "current": {},
            "confirm5_min80": {"candidateConfirmFrames": 5, "minNoteDurationMs": 80},
            "confirm7_min80": {"candidateConfirmFrames": 7, "minNoteDurationMs": 80},
            "confirm7_min120": {"candidateConfirmFrames": 7, "minNoteDurationMs": 120},
            "confirm9_min120": {"candidateConfirmFrames": 9, "minNoteDurationMs": 120},
            "confirm7_min120_gap80": {"candidateConfirmFrames": 7, "minNoteDurationMs": 120, "minGapMs": 80},
            "confirm7_min120_tol09": {"candidateConfirmFrames": 7, "minNoteDurationMs": 120, "pitchToleranceSemitones": 0.9},
            "confirm9_min160": {"candidateConfirmFrames": 9, "minNoteDurationMs": 160},
        }
    for config_name, config in configs.items():
        for threshold_text in args.thresholds.split(","):
            threshold = float(threshold_text)
            frames = []
            for x in raw:
                hz = x["frequencyHz"] if x["confidence"] >= threshold else None
                midi = 69 + 12 * __import__("math").log2(hz / 440) if hz else None
                frames.append({
                    "type": "pitch", "timestamp": x["timestamp"],
                    "frequencyHz": hz, "continuousMidi": midi,
                    "roundedMidi": round(midi) if midi is not None else None,
                    "confidence": x["confidence"], "voiced": hz is not None,
                    "algorithm": "rmvpe",
                    "diagnostics": {"rms": None, "aperiodicity": None, "clipped": False},
                })
            notes = run_segmenter(frames, args.segment_cli, config)
            metrics = evaluate(notes, ref_notes)
            tag = f"{config_name}_threshold_{threshold:g}"
            (out / f"{tag}_notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
            results[tag] = metrics

    result = {
        "raw_frames": str(Path(args.raw_frames)),
        "reference_csv": str(Path(args.ref_csv)),
        "evaluation_interval_s": {"start": args.start_time, "end_exclusive": args.end_time},
        "derived_reference_notes": len(ref_notes),
        "reference_derivation": f"nearest MIDI semitone; {args.reference_median_width}-frame median on 5.805 ms reference grid; retain runs >={args.reference_min_duration:g} s; derived from independent continuous F0 annotation, not model predictions",
        "segmentation": "project frontend/scripts/dist/segment-cli.mjs; 'current' uses defaults, other named cases override the listed NoteEventDetector parameters",
        "threshold_results": results,
    }
    (out / "note_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
