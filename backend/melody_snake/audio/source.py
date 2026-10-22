"""AudioSource abstraction: every source yields mono float32 blocks with a
sample-rate and a monotonically increasing timestamp (seconds). The pitch
engine and UI must never depend on a concrete source implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class AudioBlock:
    samples: np.ndarray  # mono float32 in [-1, 1]
    timestamp: float     # seconds since stream start, for samples[0]


class AudioSource(ABC):
    @abstractmethod
    def open(self):
        """Acquire the device / file. Raises on failure."""

    @abstractmethod
    def read(self, n_samples=None):
        """Return the next AudioBlock, or None at end of stream."""

    @abstractmethod
    def close(self):
        """Release resources. Safe to call more than once."""

    @property
    @abstractmethod
    def sample_rate(self):
        """Sample rate in Hz of the blocks this source yields."""
