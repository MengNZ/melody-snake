import numpy as np

from benchmark.waveform_periodicity import estimate_center_f0


def test_autocorrelation_recovers_a_tone_with_a_strong_second_harmonic():
    sample_rate = 44100
    time = np.arange(sample_rate) / sample_rate
    audio = 0.7 * np.sin(2 * np.pi * 123.47 * time)
    audio += 0.8 * np.sin(2 * np.pi * 246.94 * time)
    result = estimate_center_f0(audio, sample_rate, 0.2, 0.8)
    assert result is not None
    assert abs(result["frequency_hz"] - 123.47) < 1.0
    assert result["periodicity"] > 0.9
