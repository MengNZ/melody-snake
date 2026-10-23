from benchmark.target_phrase_sequence import (
    degrees_to_midi,
    evaluate_sequence,
    parse_numbered_notes,
)


def test_user_confirmed_tonic_and_written_octave_comma_are_preserved():
    notes = parse_numbered_notes("6 6 7 6 7 1, 6 6 7 6 7 1 6")
    assert degrees_to_midi(notes, tonic_midi=62) == [
        71, 71, 73, 71, 73, 50, 71, 71, 73, 71, 73, 62, 71
    ]


def test_sequence_diagnostic_separates_pitch_class_from_octave_accuracy():
    actual = [47, 47, 49, 47, 49, 50, 47]
    expected = [71, 71, 73, 71, 73, 50, 71]
    metrics = evaluate_sequence(actual, expected)
    assert metrics["pitch_class_matches"] == 7
    assert metrics["exact_midi_matches"] == 1
    assert metrics["signed_semitone_errors"] == [-24, -24, -24, -24, -24, 0, -24]


def test_sequence_alignment_handles_one_extra_predicted_note():
    expected = [47, 47, 49, 47, 49, 50, 47]
    predicted = [47, 47, 49, 47, 49, 49, 50, 47]
    metrics = evaluate_sequence(predicted, expected)
    assert metrics["sequence_aligned_pitch_class_matches"] == len(expected)
    assert metrics["sequence_aligned_exact_midi_matches"] == len(expected)
