"""Deterministic synthesis of benchmark audio with exactly-known ground truth.

Every sample's reference annotation is derived from the SAME parameters used to
synthesize it — never from the model's own predictions.
"""

import wave

import numpy as np


def write_wav(path, samples, sr):
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def silence(dur, sr):
    return np.zeros(int(dur * sr), dtype=np.float32)


def sine(freq, dur, sr, amp=0.5):
    t = np.arange(int(dur * sr), dtype=np.float64) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def piano_like(freq, dur, sr, amp=0.4, n_harmonics=8, decay=3.0):
    """Additive harmonics (1/n amplitude) with an exponential decay envelope."""
    t = np.arange(int(dur * sr), dtype=np.float64) / sr
    out = np.zeros_like(t)
    for k in range(1, n_harmonics + 1):
        out += (1.0 / k) * np.sin(2 * np.pi * freq * k * t)
    env = np.exp(-decay * t / dur)
    out *= env
    peak = np.max(np.abs(out)) or 1.0
    return (amp * out / peak).astype(np.float32)


def guitar_like(freq, dur, sr, amp=0.5, seed=0):
    """Karplus-Strong plucked string (synthetic, not a real recording)."""
    n = max(2, int(sr / freq))
    rng = np.random.default_rng(seed)
    buf = rng.uniform(-1, 1, n).astype(np.float64)
    out = np.zeros(int(dur * sr), dtype=np.float64)
    damp = 0.996
    for i in range(len(out)):
        out[i] = buf[0]
        nxt = damp * 0.5 * (buf[0] + buf[1])
        buf[:-1] = buf[1:]
        buf[-1] = nxt
    return (amp * out).astype(np.float32)


def vibrato(freq, dur, sr, amp=0.5, depth_sem=0.5, rate=5.0):
    """Frequency-modulated sine: +-depth_sem semitones at `rate` Hz."""
    t = np.arange(int(dur * sr), dtype=np.float64) / sr
    inst = freq * 2 ** (depth_sem / 12.0 * np.sin(2 * np.pi * rate * t))
    phase = 2 * np.pi * np.cumsum(inst) / sr
    return (amp * np.sin(phase)).astype(np.float32)


def glide(f1, f2, dur, sr, amp=0.5):
    """Exponential pitch glide from f1 to f2 over `dur` seconds."""
    t = np.arange(int(dur * sr), dtype=np.float64) / sr
    inst = f1 * (f2 / f1) ** (t / dur)
    phase = 2 * np.pi * np.cumsum(inst) / sr
    return (amp * np.sin(phase)).astype(np.float32)


def concat(segments, sr):
    return np.concatenate([s.astype(np.float32) for s in segments])
