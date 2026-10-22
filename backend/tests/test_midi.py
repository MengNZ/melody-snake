import pytest

from melody_snake.theory.midi import (
    A4_FREQ,
    A4_MIDI,
    continuous_midi_to_frequency,
    frequency_to_continuous_midi,
)


def test_a4_is_440hz():
    assert frequency_to_continuous_midi(440.0) == pytest.approx(A4_MIDI, abs=1e-6)
    assert continuous_midi_to_frequency(A4_MIDI) == pytest.approx(440.0, abs=1e-6)


def test_c4_c5_midi_numbers():
    assert frequency_to_continuous_midi(continuous_midi_to_frequency(60.0)) == pytest.approx(60.0, abs=1e-6)
    assert frequency_to_continuous_midi(continuous_midi_to_frequency(72.0)) == pytest.approx(72.0, abs=1e-6)


def test_invalid_frequencies_are_none():
    assert frequency_to_continuous_midi(0.0) is None
    assert frequency_to_continuous_midi(-10.0) is None
    assert frequency_to_continuous_midi(float("nan")) is None
    assert frequency_to_continuous_midi(float("inf")) is None


def test_roundtrip():
    for midi in [36.0, 60.0, 69.0, 84.0]:
        assert frequency_to_continuous_midi(continuous_midi_to_frequency(midi)) == pytest.approx(midi, abs=1e-6)


def test_semitone_ratio():
    assert continuous_midi_to_frequency(60.0) * 2.0 == pytest.approx(continuous_midi_to_frequency(72.0), abs=1e-6)
