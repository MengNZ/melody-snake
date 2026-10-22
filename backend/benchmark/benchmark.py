"""Benchmark: WAV + reference -> full pipeline -> note-level metrics.

Runs YIN (Python) -> pitch frames -> segmentation (bundled TS CLI) -> metrics.
Outputs a per-sample metrics.json plus an appending summary.csv.
"""

import argparse
import csv
import json
import os
import subprocess
import tempfile
from pathlib import Path

from melody_snake.audio.file_source import read_wav_mono
from melody_snake.engine import process_audio

from .metrics import evaluate

DEFAULT_SEGMENT_CLI = Path(__file__).resolve().parents[2] / "frontend" / "scripts" / "dist" / "segment-cli.mjs"

CSV_COLUMNS = [
    "name", "n_reference", "n_predicted", "hits", "false_negatives", "false_positives",
    "octave_errors", "wrong_pitch", "note_precision", "note_recall", "f1",
    "pitch_accuracy", "octave_error_rate", "mean_abs_onset_error_s",
]


def run_pipeline(wav_path, segment_cli=DEFAULT_SEGMENT_CLI):
    """WAV -> (notes, sample_rate)."""
    samples, sr = read_wav_mono(str(wav_path))
    frames = process_audio(samples, sr)
    with tempfile.TemporaryDirectory() as td:
        frames_path = os.path.join(td, "frames.json")
        notes_path = os.path.join(td, "notes.json")
        with open(frames_path, "w", encoding="utf-8") as f:
            json.dump(frames, f)
        proc = subprocess.run(
            ["node", str(segment_cli), frames_path, notes_path],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"segment-cli failed: {proc.stderr}")
        with open(notes_path, encoding="utf-8") as f:
            notes = json.load(f)
    return notes, sr


def benchmark_sample(wav, ref, segment_cli=DEFAULT_SEGMENT_CLI):
    ref_data = json.loads(Path(ref).read_text(encoding="utf-8")) if isinstance(ref, (str, Path)) else ref
    notes, sr = run_pipeline(wav, segment_cli)
    metrics = evaluate(notes, ref_data)
    return metrics, notes, sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav")
    ap.add_argument("--ref")
    ap.add_argument("--dataset")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "summary.csv"
    write_header = not summary_path.exists()

    jobs = []
    if args.dataset:
        d = Path(args.dataset)
        for refp in sorted(d.glob("*.ref.json")):
            name = refp.name[: -len(".ref.json")]
            wav = d / f"{name}.wav"
            if wav.exists():
                jobs.append((name, wav, refp))
    elif args.wav and args.ref:
        name = Path(args.wav).stem
        jobs.append((name, Path(args.wav), Path(args.ref)))
    else:
        ap.error("provide --wav/--ref or --dataset")

    with open(summary_path, "a", newline="", encoding="utf-8") as csvf:
        writer = csv.DictWriter(csvf, fieldnames=CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        for name, wav, ref in jobs:
            metrics, notes, sr = benchmark_sample(wav, ref)
            report = {
                "name": name,
                "sample_rate": sr,
                "metrics": metrics,
                "predicted_notes": notes,
                "reference_notes": json.loads(Path(ref).read_text(encoding="utf-8")),
            }
            (out / f"{name}.metrics.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            row = {c: metrics.get(c) for c in CSV_COLUMNS}
            row["name"] = name
            for c in CSV_COLUMNS[1:]:
                v = row[c]
                if isinstance(v, float):
                    row[c] = f"{v:.4f}"
            writer.writerow(row)
            print(f"[{name}] precision={metrics['note_precision']:.2f} recall={metrics['note_recall']:.2f} "
                  f"f1={metrics['f1']:.2f} pitch_acc={metrics['pitch_accuracy']:.2f} oct={metrics['octave_errors']}")

    print(f"summary -> {summary_path}")


if __name__ == "__main__":
    main()
