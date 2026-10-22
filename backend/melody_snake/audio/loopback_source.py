"""WASAPI loopback capture (system playback audio) via pyaudiowpatch."""

import numpy as np
import pyaudiowpatch as pyaudio

from .source import AudioBlock, AudioSource


class LoopbackSource(AudioSource):
    def __init__(self, device_index=None, block_size=1024):
        self.device_index = device_index  # None -> default loopback device
        self.block_size = block_size
        self._pa = None
        self._stream = None
        self._sr = 0
        self._channels = 0
        self._elapsed = 0.0

    def open(self):
        self._pa = pyaudio.PyAudio()
        if self.device_index is None:
            info = self._pa.get_default_wasapi_loopback()
        else:
            info = next(
                (d for d in self._pa.get_loopback_device_info_generator()
                 if d["index"] == self.device_index),
                None,
            )
            if info is None:
                self._pa.terminate()
                raise RuntimeError(f"No loopback device at index {self.device_index}")

        self.device_index = int(info["index"])
        self._sr = int(info["defaultSampleRate"])
        self._channels = int(info["maxInputChannels"])
        self._stream = self._pa.open(
            format=pyaudio.paFloat32,
            channels=self._channels,
            rate=self._sr,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=self.block_size,
        )

    @property
    def sample_rate(self):
        return self._sr

    def read(self, n_samples=None):
        if self._stream is None:
            return None
        n = n_samples or self.block_size
        try:
            data = self._stream.read(n, exception_on_overflow=False)
        except OSError:
            return None

        arr = np.frombuffer(data, dtype=np.float32)
        if self._channels > 1:
            mono = arr.reshape(-1, self._channels).mean(axis=1).astype(np.float32)
        else:
            mono = arr.astype(np.float32)

        timestamp = self._elapsed
        self._elapsed += len(mono) / self._sr
        return AudioBlock(samples=mono, timestamp=timestamp)

    def close(self):
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except OSError:
                pass
            self._stream = None
        if self._pa is not None:
            try:
                self._pa.terminate()
            except OSError:
                pass
            self._pa = None
