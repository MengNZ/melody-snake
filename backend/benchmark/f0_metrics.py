"""Frame-level F0 evaluation against a time-aligned melody reference.

Rows are dictionaries with ``time`` (seconds) and ``f0_hz`` (0/None = unvoiced).
Predictions can be engine PitchEstimate dictionaries. Each reference frame
independently uses its nearest prediction, allowing different frame hop sizes
without dropping valid reference frames.
"""
from bisect import bisect_left
import math


def _hz_to_midi(hz):
    return 69.0 + 12.0 * math.log2(hz / 440.0) if hz and hz > 0 else None


def evaluate_f0(reference, predicted, tolerance_cents=50.0, max_time_delta_s=0.012, prediction_time_offset_s=0.0):
    ref = sorted(reference, key=lambda x: x["time"])
    pred = sorted(predicted, key=lambda x: x["timestamp"])
    pt = [x["timestamp"] + prediction_time_offset_s for x in pred]
    mapped = []
    for r in ref:
        i = bisect_left(pt, r["time"])
        candidates = [j for j in (i - 1, i) if 0 <= j < len(pred)]
        j = min(candidates, key=lambda j: abs(pt[j] - r["time"])) if candidates else None
        if j is None or abs(pt[j] - r["time"]) > max_time_delta_s:
            mapped.append((r, None))
        else:
            mapped.append((r, pred[j]))

    ref_voiced = pred_voiced = true_voiced = raw_hits = chroma_hits = octave_errors = 0
    cents_errors = []
    evaluated = 0
    for r, p in mapped:
        evaluated += 1
        rm = _hz_to_midi(r.get("f0_hz"))
        pm = _hz_to_midi((p or {}).get("frequencyHz"))
        if rm is not None:
            ref_voiced += 1
        if pm is not None:
            pred_voiced += 1
        if rm is None or pm is None:
            continue
        true_voiced += 1
        diff = pm - rm
        cents = abs(diff) * 100.0
        cents_errors.append(cents)
        if cents <= tolerance_cents:
            raw_hits += 1
            chroma_hits += 1
        else:
            chroma_diff = abs(((diff + 6.0) % 12.0) - 6.0)
            if chroma_diff * 100.0 <= tolerance_cents:
                chroma_hits += 1
                if 11.5 <= abs(diff) <= 12.5:
                    octave_errors += 1

    sorted_errors = sorted(cents_errors)
    n_err = len(sorted_errors)
    median_cents = (sorted_errors[n_err // 2] if n_err % 2 else
                    (sorted_errors[n_err // 2 - 1] + sorted_errors[n_err // 2]) / 2) if n_err else None
    return {
        "reference_frames": len(ref),
        "mapped_frames": evaluated,
        "unmapped_reference_frames": sum(p is None for _, p in mapped),
        "reference_voiced_frames": ref_voiced,
        "predicted_voiced_on_mapped_frames": pred_voiced,
        "true_voiced_frames": true_voiced,
        "voicing_recall": true_voiced / ref_voiced if ref_voiced else 0.0,
        "voicing_precision_on_mapped_frames": true_voiced / pred_voiced if pred_voiced else 0.0,
        "raw_pitch_accuracy": raw_hits / ref_voiced if ref_voiced else 0.0,
        "chroma_accuracy": chroma_hits / ref_voiced if ref_voiced else 0.0,
        "octave_errors": octave_errors,
        "octave_error_rate_of_voiced_matches": octave_errors / true_voiced if true_voiced else 0.0,
        "median_abs_cents_when_both_voiced": median_cents,
        "pitch_tolerance_cents": tolerance_cents,
        "max_time_delta_s": max_time_delta_s,
        "prediction_time_offset_s": prediction_time_offset_s,
        "definitions": {
            "alignment": "each reference frame independently uses its nearest prediction within max_time_delta_s; prediction frames may be reused so systems with different hop sizes can be compared",
            "raw_pitch_accuracy": "reference-voiced frames whose predicted F0 is within tolerance_cents; denominator is all reference-voiced frames, so missed voicing counts wrong",
            "chroma_accuracy": "reference-voiced frames within tolerance after octave-equivalent pitch-class comparison; denominator is all reference-voiced frames",
            "voicing_recall": "both voiced / reference voiced frames",
            "voicing_precision_on_mapped_frames": "both voiced / predicted voiced among mapped reference frames; unmatched extra prediction frames are not counted",
        },
    }
