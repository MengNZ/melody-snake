from benchmark.f0_metrics import evaluate_f0


def test_f0_alignment_allows_different_hop_sizes():
    reference = [
        {"time": 0.0, "f0_hz": 440.0},
        {"time": 0.005805, "f0_hz": 440.0},
        {"time": 0.01161, "f0_hz": 440.0},
    ]
    predicted = [
        {"timestamp": 0.0, "frequencyHz": 440.0},
        {"timestamp": 0.01, "frequencyHz": 440.0},
    ]

    result = evaluate_f0(reference, predicted, max_time_delta_s=0.006)

    assert result["mapped_frames"] == 3
    assert result["unmapped_reference_frames"] == 0
    assert result["raw_pitch_accuracy"] == 1.0


def test_f0_alignment_still_respects_maximum_time_delta():
    result = evaluate_f0(
        [{"time": 1.0, "f0_hz": 440.0}],
        [{"timestamp": 0.0, "frequencyHz": 440.0}],
        max_time_delta_s=0.01,
    )

    assert result["unmapped_reference_frames"] == 1
    assert result["raw_pitch_accuracy"] == 0.0
