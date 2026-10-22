"""Frequency <-> MIDI conversions. Mirrors the TS core/midi.ts contract."""

import math

A4_MIDI = 69
A4_FREQ = 440.0


def frequency_to_continuous_midi(freq_hz):
    """m = 69 + 12 * log2(f / 440). Returns None for invalid/zero/negative/NaN."""
    if freq_hz is None or freq_hz <= 0 or not math.isfinite(freq_hz):
        return None
    return A4_MIDI + 12.0 * math.log2(freq_hz / A4_FREQ)


def continuous_midi_to_frequency(midi):
    """f = 440 * 2^((m - 69) / 12)."""
    return A4_FREQ * 2.0 ** ((midi - A4_MIDI) / 12.0)
