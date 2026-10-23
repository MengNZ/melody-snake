"""Run the actual backend transcription entrypoint on a reference WAV."""

import argparse
import json
from pathlib import Path

from benchmark.f0_metrics import evaluate_f0
from benchmark.rmvpe_note_benchmark import derive_reference_notes
from benchmark.f0_benchmark import read_reference as read_f0_reference
from benchmark.metrics import evaluate as evaluate_notes
from melody_snake.transcribe import RMVPE_SEGMENTATION_CONFIG, extract_notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--ref-csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument("--reference-min-duration", type=float, default=0.12)
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    frames_path = out / "project_pitch_frames.json"
    notes, sample_rate = extract_notes(
        args.wav, frames_out=frames_path, pitch_method="rmvpe",
        confidence_threshold=args.threshold,
        segmentation_config=RMVPE_SEGMENTATION_CONFIG,
    )
    (out / "project_notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

    reference = read_f0_reference(args.ref_csv)
    frames = json.loads(frames_path.read_text(encoding="utf-8"))
    f0_metrics = evaluate_f0(reference, frames, max_time_delta_s=0.012)
    reference_note_rows = [
        (row["time"], round(69 + 12 * __import__("math").log2(row["f0_hz"] / 440.0)) if row["f0_hz"] > 0 else None)
        for row in reference
    ]
    reference_notes = derive_reference_notes(reference_note_rows, min_duration_s=args.reference_min_duration)
    note_metrics = evaluate_notes(notes, reference_notes)
    result = {
        "wav": str(Path(args.wav)),
        "reference": str(Path(args.ref_csv)),
        "sample_rate": sample_rate,
        "pitch_method": "RMVPE ONNX via backend.melody_snake.transcribe.extract_notes",
        "confidence_threshold": args.threshold,
        "segmentation_config": RMVPE_SEGMENTATION_CONFIG,
        "frame_metrics": f0_metrics,
        "note_metrics": note_metrics,
        "note_reference_count": len(reference_notes),
        "note_reference_derivation": f"nearest MIDI semitone; five-frame median; retain runs >={args.reference_min_duration:g} s",
    }
    (out / "project_route_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
