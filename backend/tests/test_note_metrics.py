from benchmark.metrics import evaluate


def _note(midi, start, end):
    return {"midiNote": midi, "startTime": start, "endTime": end}


def test_adjacent_interval_metrics_distinguish_octave():
    reference = [
        {"midi": 60, "start": 0.0, "end": 1.0},
        {"midi": 62, "start": 1.0, "end": 2.0},
        {"midi": 64, "start": 2.0, "end": 3.0},
    ]
    predicted = [
        _note(60, 0.0, 1.0),
        _note(74, 1.0, 2.0),
        _note(64, 2.0, 3.0),
    ]

    metrics = evaluate(predicted, reference)

    assert metrics["adjacent_interval_pairs"] == 2
    assert metrics["interval_accuracy"] == 0.0
    assert metrics["pitch_class_interval_accuracy"] == 1.0


def test_interval_denominator_excludes_unmatched_reference_edges():
    reference = [
        {"midi": 60, "start": 0.0, "end": 1.0},
        {"midi": 62, "start": 1.0, "end": 2.0},
        {"midi": 64, "start": 2.0, "end": 3.0},
    ]
    predicted = [_note(60, 0.0, 1.0), _note(64, 2.0, 3.0)]

    metrics = evaluate(predicted, reference)

    assert metrics["adjacent_interval_pairs"] == 0
    assert metrics["interval_accuracy"] is None
    assert metrics["pitch_class_interval_accuracy"] is None
