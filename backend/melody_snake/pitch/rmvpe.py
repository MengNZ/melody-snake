"""RMVPE ONNX pitch estimation for polyphonic vocal audio.

The model layout, cents conversion, and local-average decoding follow the
MIT-licensed RVC/RMVPE implementation by liujing04, 源文雨, and Ftps. This
module keeps preprocessing self-contained because importing librosa.filters
hangs in the current Windows runtime. Model weights are downloaded separately
with ``python -m benchmark.download_rmvpe_model``.
"""

import hashlib
import os
from functools import lru_cache
from math import gcd
from pathlib import Path

import numpy as np
import onnxruntime as ort
from scipy.signal import get_window, resample_poly

from ..theory.midi import frequency_to_continuous_midi

SAMPLE_RATE = 16_000
WIN_LENGTH = 1024
HOP_LENGTH = 160
N_MELS = 128
N_CLASSES = 360
MEL_FMIN = 30.0
MEL_FMAX = 8_000.0
CENTS_OFFSET = 1997.3794084376191
MODEL_SHA256 = "5370e71ac80af8b4b7c793d27efd51fd8bf962de3a7ede0766dac0befa3660fd"


def default_model_path():
    configured = os.environ.get("MELODY_SNAKE_RMVPE_MODEL")
    if configured:
        return Path(configured)
    root = Path(__file__).resolve().parents[3]
    candidates = (root / "backend" / "models" / "rmvpe.onnx", root / "recordings" / "rmvpe_model.onnx")
    return next((path for path in candidates if path.is_file()), candidates[0])


def _check_model_checksum(path):
    digest = hashlib.sha256()
    with open(path, "rb") as model:
        for block in iter(lambda: model.read(1024 * 1024), b""):
            digest.update(block)
    actual = digest.hexdigest()
    if actual != MODEL_SHA256:
        raise ValueError(f"RMVPE model SHA-256 mismatch: expected {MODEL_SHA256}, got {actual}")


@lru_cache(maxsize=1)
def _mel_basis():
    """HTK triangular filter bank equivalent to librosa's norm=None version."""
    hz_to_mel = lambda hz: 2595.0 * np.log10(1.0 + hz / 700.0)
    mel_to_hz = lambda mel: 700.0 * (10.0 ** (mel / 2595.0) - 1.0)
    mel_points = np.linspace(hz_to_mel(MEL_FMIN), hz_to_mel(MEL_FMAX), N_MELS + 2)
    mel_frequencies = mel_to_hz(mel_points)
    fft_frequencies = np.arange(1 + WIN_LENGTH // 2, dtype=np.float64) * (SAMPLE_RATE / WIN_LENGTH)
    differences = np.diff(mel_frequencies)
    ramps = mel_frequencies[:, None] - fft_frequencies[None, :]
    weights = np.zeros((N_MELS, 1 + WIN_LENGTH // 2), dtype=np.float32)
    for index in range(N_MELS):
        lower = -ramps[index] / differences[index]
        upper = ramps[index + 2] / differences[index + 1]
        weights[index] = np.maximum(0.0, np.minimum(lower, upper))
    return weights


def _mono_16k(audio, sample_rate):
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)
    if audio.ndim != 1:
        raise ValueError("RMVPE expects mono samples or samples shaped (frames, channels)")
    if sample_rate != SAMPLE_RATE:
        divisor = gcd(int(sample_rate), SAMPLE_RATE)
        audio = resample_poly(audio, SAMPLE_RATE // divisor, int(sample_rate) // divisor)
    return np.asarray(audio, dtype=np.float32)


def _mel_spectrogram(audio):
    if len(audio) == 0:
        return np.zeros((N_MELS, 0), dtype=np.float32)
    window = get_window("hann", WIN_LENGTH, fftbins=True).astype(np.float32)
    pad_mode = "reflect" if len(audio) > 1 else "edge"
    padded = np.pad(audio, WIN_LENGTH // 2, mode=pad_mode)
    shape = ((padded.size - WIN_LENGTH) // HOP_LENGTH + 1, WIN_LENGTH)
    strides = (padded.strides[0] * HOP_LENGTH, padded.strides[0])
    frames = np.lib.stride_tricks.as_strided(padded, shape=shape, strides=strides)
    magnitude = np.abs(np.fft.rfft(frames * window, n=WIN_LENGTH)).T.astype(np.float32)
    return np.log(np.clip(_mel_basis() @ magnitude, 1e-5, None))


class RMVPEEstimator:
    """CPU ONNX Runtime wrapper. The model itself is not stored in Git."""

    def __init__(self, model_path=None, intra_op_threads=4):
        self.model_path = Path(model_path) if model_path else default_model_path()
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"RMVPE weights not found at {self.model_path}; run "
                "`python -m benchmark.download_rmvpe_model` or set MELODY_SNAKE_RMVPE_MODEL"
            )
        _check_model_checksum(self.model_path)
        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.intra_op_num_threads = max(1, int(intra_op_threads))
        self.session = ort.InferenceSession(
            str(self.model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        cents = 20 * np.arange(N_CLASSES) + CENTS_OFFSET
        self.cents_mapping = np.pad(cents, (4, 4))

    def predict(self, audio, sample_rate):
        audio = _mono_16k(audio, sample_rate)
        mel = _mel_spectrogram(audio)
        frame_count = mel.shape[1]
        if frame_count == 0:
            empty = np.zeros(0, dtype=np.float32)
            return empty, empty, empty
        padded_count = 32 * ((frame_count - 1) // 32 + 1)
        if padded_count > frame_count:
            mel = np.pad(mel, ((0, 0), (0, padded_count - frame_count)))
        activation = self.session.run(
            [self.output_name], {self.input_name: mel[np.newaxis]}
        )[0][0, :frame_count].astype(np.float32)
        confidence = activation.max(axis=1)
        centers = np.argmax(activation, axis=1) + 4
        padded = np.pad(activation, ((0, 0), (4, 4)))
        columns = centers[:, None] - 4 + np.arange(9)[None, :]
        local = padded[np.arange(frame_count)[:, None], columns]
        cents = (local * self.cents_mapping[columns]).sum(axis=1) / np.maximum(local.sum(axis=1), 1e-12)
        frequencies = 10.0 * (2.0 ** (cents / 1200.0))
        times = np.arange(frame_count, dtype=np.float64) * (HOP_LENGTH / SAMPLE_RATE)
        return times, frequencies.astype(np.float32), confidence.astype(np.float32)


def process_audio_rmvpe(samples, sample_rate, min_confidence=0.6, model_path=None,
                         start_timestamp=0.0, estimator=None):
    """Return app-contract PitchEstimate frames from arbitrary audio samples."""
    estimator = estimator or RMVPEEstimator(model_path=model_path)
    times, frequencies, confidences = estimator.predict(samples, sample_rate)
    result = []
    for time_s, frequency, confidence in zip(times, frequencies, confidences):
        voiced = float(confidence) >= min_confidence
        hz = float(frequency) if voiced else None
        midi = frequency_to_continuous_midi(hz) if hz is not None else None
        result.append({
            "type": "pitch",
            "timestamp": float(start_timestamp + time_s),
            "frequencyHz": hz,
            "continuousMidi": midi,
            "roundedMidi": round(midi) if midi is not None else None,
            "confidence": float(confidence),
            "voiced": voiced,
            "algorithm": "rmvpe-onnx",
            "diagnostics": {"aperiodicity": float(1.0 - confidence)},
        })
    return result
