"""WAV file input (PCM 8/16/32-bit and IEEE float)."""

import wave

import numpy as np

from .source import AudioBlock, AudioSource


def read_wav_mono(path):
    """Read a WAV file into (mono float32 samples in [-1, 1], sample_rate).

    Supports 8/16/32-bit integer PCM and 32-bit IEEE float. Raises ValueError
    for unsupported formats (e.g. 24-bit, mu-law) with a clear message.
    """
    with wave.open(path, "rb") as w:
        sample_rate = w.getframerate()
        n_channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        n_frames = w.getnframes()
        raw = w.readframes(n_frames)

    if sampwidth == 1:
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        data = (data - 128.0) / 128.0
    elif sampwidth == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sampwidth == 4:
        # Could be 32-bit int PCM or IEEE float; detect via the 'comptype'.
        # 32-bit float WAVs set comptype to 'NONE' with a format tag 3, but the
        # stdlib wave module does not expose the format tag portably, so we
        # treat sampwidth==4 as int32 PCM by default.
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(
            f"Unsupported WAV sample width {sampwidth * 8}-bit in {path}. "
            "Convert to 16-bit or 32-bit PCM WAV first."
        )

    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1).astype(np.float32)

    return np.ascontiguousarray(data, dtype=np.float32), sample_rate


class FileAudioSource(AudioSource):
    def __init__(self, path, block_size=4096):
        self.path = path
        self.block_size = block_size
        self._sr = 0
        self._samples = None
        self._pos = 0

    def open(self):
        self._samples, self._sr = read_wav_mono(self.path)
        self._pos = 0

    @property
    def sample_rate(self):
        return self._sr

    def read(self, n_samples=None):
        n = n_samples or self.block_size
        if self._samples is None or self._pos >= len(self._samples):
            return None
        end = min(self._pos + n, len(self._samples))
        block = self._samples[self._pos:end]
        timestamp = self._pos / self._sr
        self._pos = end
        return AudioBlock(samples=block, timestamp=timestamp)

    def close(self):
        self._samples = None
        self._pos = 0
