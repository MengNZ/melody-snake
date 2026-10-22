"""Pitch engine: turns raw mono samples into a stream of PitchEstimate dicts.

The dict shape matches the TypeScript `PitchEstimate` JSON contract exactly
(camelCase keys), so the frontend consumes it with no conversion layer.
"""

import numpy as np

from .pitch.yin import YinDetector
from .theory.midi import frequency_to_continuous_midi

DEFAULT_FRAME_SIZE = 2048
DEFAULT_HOP = 512


def detect_frame(detector, window, sample_rate, timestamp):
    """Run YIN on one window and return a PitchEstimate dict (JSON contract)."""
    f0, confidence, rms, clipped = detector.detect(window, sample_rate)
    midi = frequency_to_continuous_midi(f0) if f0 is not None else None
    return {
        "type": "pitch",
        "timestamp": float(timestamp),
        "frequencyHz": f0 if f0 is not None else None,
        "continuousMidi": midi,
        "roundedMidi": round(midi) if midi is not None else None,
        "confidence": float(confidence),
        "voiced": f0 is not None,
        "algorithm": "yin",
        "diagnostics": {
            "rms": rms,
            "aperiodicity": 1.0 - confidence,
            "clipped": clipped,
        },
    }


def process_audio(samples, sample_rate, hop=DEFAULT_HOP, frame_size=DEFAULT_FRAME_SIZE,
                  detector=None, start_timestamp=0.0):
    """Offline processing of a whole mono float32 array -> list of pitch frames."""
    detector = detector or YinDetector()
    samples = np.asarray(samples, dtype=np.float32)
    n = len(samples)

    frames = []
    i = 0
    while i + frame_size <= n:
        window = samples[i:i + frame_size]
        timestamp = start_timestamp + i / sample_rate
        frames.append(detect_frame(detector, window, sample_rate, timestamp))
        i += hop
    return frames


class StreamingPitchProcessor:
    """Incrementally turns pushed sample blocks into pitch frames (real-time path).

    Maintains an internal buffer; emits a frame every `hop` samples once at
    least `frame_size` samples are buffered. Timestamps are sample-accurate
    (samples_consumed / sample_rate), independent of wall clock.
    """

    def __init__(self, sample_rate, hop=DEFAULT_HOP, frame_size=DEFAULT_FRAME_SIZE,
                 detector=None, on_frame=None):
        self.sample_rate = int(sample_rate)
        self.hop = int(hop)
        self.frame_size = int(frame_size)
        self.detector = detector or YinDetector()
        self.on_frame = on_frame
        self._buffer = np.zeros(0, dtype=np.float32)
        self._consumed = 0

    def push(self, samples):
        samples = np.asarray(samples, dtype=np.float32)
        self._buffer = np.concatenate([self._buffer, samples])

        while len(self._buffer) >= self.frame_size:
            window = self._buffer[:self.frame_size]
            timestamp = self._consumed / self.sample_rate
            frame = detect_frame(self.detector, window, self.sample_rate, timestamp)
            if self.on_frame is not None:
                self.on_frame(frame)
            self._buffer = self._buffer[self.hop:]
            self._consumed += self.hop

    def flush(self):
        """Drop any leftover samples that never formed a full frame."""
        self._buffer = np.zeros(0, dtype=np.float32)
