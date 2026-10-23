"""Check note-center F0 directly from waveform periodicity, without a pitch model.

This checks pitch in the center of existing note events. It does not verify
their onset/offset boundaries or whether the note sequence itself is complete.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import correlate, find_peaks


def estimate_center_f0(audio, sample_rate, start_time, end_time, window_s=0.11,
                       min_frequency=75.0, max_frequency=260.0):
    duration = end_time - start_time
    if duration <= 0:
        return None
    width = min(window_s, duration * 0.8)
    center = (start_time + end_time) / 2
    left = round((center - width / 2) * sample_rate)
    right = round((center + width / 2) * sample_rate)
    x = np.asarray(audio[max(0, left):min(len(audio), right)], dtype=np.float64)
    if x.size < 32:
        return None
    x -= x.mean()
    x *= np.hanning(x.size)
    autocorr = correlate(x, x, mode="full", method="fft")[x.size - 1:]
    if autocorr.size == 0 or autocorr[0] <= 0:
        return None
    autocorr /= autocorr[0]
    low_lag = max(1, round(sample_rate / max_frequency))
    high_lag = min(len(autocorr) - 1, round(sample_rate / min_frequency))
    if high_lag <= low_lag:
        return None
    peaks, _ = find_peaks(autocorr[low_lag:high_lag + 1])
    if peaks.size == 0:
        return None
    lag = low_lag + int(peaks[np.argmax(autocorr[low_lag:high_lag + 1][peaks])])
    offset = 0.0
    if 0 < lag < len(autocorr) - 1:
        denominator = autocorr[lag - 1] - 2 * autocorr[lag] + autocorr[lag + 1]
        if denominator != 0:
            offset = 0.5 * (autocorr[lag - 1] - autocorr[lag + 1]) / denominator
    refined_lag = lag + offset
    return {
        "frequency_hz": float(sample_rate / refined_lag),
        "periodicity": float(autocorr[lag]),
        "window_start_s": float(center - width / 2),
        "window_end_s": float(center + width / 2),
    }


def check_notes(audio, sample_rate, notes, tolerance_cents=50.0):
    results = []
    for note in notes:
        estimate = estimate_center_f0(
            audio, sample_rate, note["startTime"], note["endTime"]
        )
        if estimate is None:
            results.append({"noteName": note["noteName"], "match": False, "estimate": None})
            continue
        midi = 69 + 12 * math.log2(estimate["frequency_hz"] / 440.0)
        cents = 100 * (midi - note["midiNote"])
        results.append({
            "noteName": note["noteName"],
            "midiNote": note["midiNote"],
            "estimatedMidi": midi,
            "centsError": cents,
            "match": abs(cents) <= tolerance_cents,
            "estimate": estimate,
        })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wav", required=True, type=Path)
    parser.add_argument("--notes", required=True, type=Path)
    parser.add_argument("--count", type=int, default=13)
    parser.add_argument("--tolerance-cents", type=float, default=50.0)
    args = parser.parse_args()

    sample_rate, audio = wavfile.read(args.wav)
    if audio.ndim == 2:
        audio = audio.astype(np.float64).mean(axis=1)
    else:
        audio = audio.astype(np.float64)
    notes = json.loads(args.notes.read_text(encoding="utf-8"))[:args.count]
    results = check_notes(audio, sample_rate, notes, args.tolerance_cents)
    output = {
        "wav": str(args.wav),
        "notes_checked": len(results),
        "periodicity_pitch_matches": sum(row["match"] for row in results),
        "tolerance_cents": args.tolerance_cents,
        "boundary_accuracy_evaluated": False,
        "results": results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
