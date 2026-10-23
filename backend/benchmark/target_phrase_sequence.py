"""Sequence-only pitch diagnostic for a lyric-aligned user jianpu phrase.

This deliberately does not score note boundaries or claim independent ground
truth: the notation is user supplied and may omit octave marks.
"""

import argparse
import json
import re
from pathlib import Path


MAJOR_SCALE_SEMITONES = (0, 2, 4, 5, 7, 9, 11)


def parse_numbered_notes(notation):
    """Return (scale degree, octave offset) pairs; a trailing comma is -1 octave."""
    return [
        (int(degree), -12 * len(commas))
        for degree, commas in re.findall(r"(?<!\d)([1-7])(,*)", notation)
    ]


def degrees_to_midi(degrees, tonic_midi):
    """Map explicit (degree, octave offset) tokens from the declared tonic."""
    pitches = []
    for token in degrees:
        degree, octave_offset = token if isinstance(token, tuple) else (token, 0)
        pitches.append(tonic_midi + MAJOR_SCALE_SEMITONES[degree - 1] + octave_offset)
    return pitches


def evaluate_sequence(predicted, expected):
    compared = min(len(predicted), len(expected))
    errors = [predicted[i] - expected[i] for i in range(compared)]
    pitch_class_lcs = _lcs_matches(
        [pitch % 12 for pitch in predicted], [pitch % 12 for pitch in expected]
    )
    absolute_lcs = _lcs_matches(predicted, expected)
    return {
        "expected_count": len(expected),
        "predicted_count": len(predicted),
        "compared_count": compared,
        "pitch_class_matches": sum(error % 12 == 0 for error in errors),
        "exact_midi_matches": sum(error == 0 for error in errors),
        "signed_semitone_errors": errors,
        "sequence_aligned_pitch_class_matches": pitch_class_lcs,
        "sequence_aligned_exact_midi_matches": absolute_lcs,
        "sequence_aligned_pitch_class_recall": pitch_class_lcs / len(expected) if expected else 0.0,
        "sequence_aligned_exact_midi_recall": absolute_lcs / len(expected) if expected else 0.0,
        "prediction_exhausted": len(predicted) < len(expected),
        "interpretation": "sequence-only diagnostic; does not evaluate timing and user notation may omit octave marks",
    }


def _lcs_matches(predicted, expected):
    rows = len(predicted) + 1
    cols = len(expected) + 1
    table = [[0] * cols for _ in range(rows)]
    for i in range(1, rows):
        for j in range(1, cols):
            if predicted[i - 1] == expected[j - 1]:
                table[i][j] = table[i - 1][j - 1] + 1
            else:
                table[i][j] = max(table[i - 1][j], table[i][j - 1])
    return table[-1][-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--notes", required=True, type=Path)
    parser.add_argument("--phrase", type=int, default=0)
    parser.add_argument("--candidate-count", type=int,
                        help="Optional number of leading predicted events to align, allowing extras")
    parser.add_argument("--tonic-midi", type=int, required=True,
                        help="MIDI pitch for unmarked scale degree 1 (D4 = 62)")
    args = parser.parse_args()

    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    predicted_rows = json.loads(args.notes.read_text(encoding="utf-8"))
    phrase = reference["phrases"][args.phrase]
    numbered_notes = parse_numbered_notes(phrase["number_notation_original"])
    degrees = [degree for degree, _ in numbered_notes]
    expected = degrees_to_midi(numbered_notes, args.tonic_midi)
    candidate_count = args.candidate_count or len(expected)
    predicted = [int(row["midiNote"]) for row in predicted_rows[:candidate_count]]
    result = {
        "phrase": phrase["lyrics"],
        "notation": phrase["number_notation_original"],
        "tonic_midi": args.tonic_midi,
        "degrees": degrees,
        "octave_offsets": [octave for _, octave in numbered_notes],
        "expected_midi": expected,
        "predicted_midi": predicted,
        "candidate_count": candidate_count,
        **evaluate_sequence(predicted, expected),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
