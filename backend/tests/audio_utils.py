"""Helpers to synthesize deterministic test audio."""

import numpy as np


def sine(freq_hz, duration_s, sample_rate=44100, amp=0.5):
    """A constant-amplitude sine tone as mono float32."""
    t = np.arange(int(duration_s * sample_rate), dtype=np.float64) / sample_rate
    return (amp * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)
