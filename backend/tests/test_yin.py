import numpy as np
import pytest

from melody_snake.pitch.yin import YinDetector
from tests.audio_utils import sine


@pytest.fixture()
def sr():
    return 44100


def test_detects_440hz(sr):
    x = sine(440.0, 2048 / sr, sr)
    f0, conf, rms, clipped = YinDetector().detect(x, sr)
    assert f0 is not None
    assert abs(f0 - 440.0) < 2.0
    assert conf > 0.5
    assert rms > 0.1
    assert clipped is False


def test_detects_c4(sr):
    x = sine(261.6256, 2048 / sr, sr)
    f0, conf, _, _ = YinDetector().detect(x, sr)
    assert f0 is not None
    assert abs(f0 - 261.6256) < 2.0
    assert conf > 0.5


def test_detects_low_and_high_notes(sr):
    det = YinDetector()
    for freq in [82.41, 440.0, 880.0]:
        x = sine(freq, 4096 / sr, sr)
        f0, conf, _, _ = det.detect(x, sr)
        assert f0 is not None, f"failed at {freq} Hz"
        assert abs(f0 - freq) < 3.0, f"{freq} Hz -> {f0} Hz"


def test_silence_is_unvoiced(sr):
    x = np.zeros(2048, dtype=np.float32)
    f0, conf, rms, _ = YinDetector().detect(x, sr)
    assert f0 is None
    assert rms < 1e-3


def test_white_noise_is_unvoiced(sr):
    rng = np.random.default_rng(0)
    x = rng.standard_normal(2048).astype(np.float32)
    f0, conf, _, _ = YinDetector().detect(x, sr)
    assert f0 is None or conf < 0.3
