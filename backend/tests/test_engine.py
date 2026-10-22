import numpy as np

from melody_snake.engine import DEFAULT_FRAME_SIZE, DEFAULT_HOP, process_audio
from melody_snake.theory.midi import continuous_midi_to_frequency
from tests.audio_utils import sine


def test_process_audio_detects_c4_e4_d4_g4():
    sr = 44100
    notes = [60, 64, 62, 67]
    segs = [sine(continuous_midi_to_frequency(m), 0.4, sr) for m in notes]
    gap = np.zeros(int(0.1 * sr), dtype=np.float32)
    samples = np.concatenate([segs[0], gap, segs[1], gap, segs[2], gap, segs[3]])

    frames = process_audio(samples, sr)

    voiced = [f for f in frames if f["voiced"] and f["confidence"] > 0.5]
    seq = []
    for f in voiced:
        m = f["roundedMidi"]
        if not seq or m != seq[-1]:
            seq.append(m)

    assert seq == notes


def test_process_audio_timestamps_are_monotonic():
    sr = 44100
    samples = sine(440.0, 1.0, sr)
    frames = process_audio(samples, sr)
    assert len(frames) > 0
    for a, b in zip(frames, frames[1:]):
        assert b["timestamp"] > a["timestamp"]


def test_process_audio_frame_count_matches_hop():
    sr = 44100
    samples = sine(440.0, 1.0, sr)
    frames = process_audio(samples, sr, hop=DEFAULT_HOP, frame_size=DEFAULT_FRAME_SIZE)
    expected = (len(samples) - DEFAULT_FRAME_SIZE) // DEFAULT_HOP + 1
    assert len(frames) == expected


def test_process_audio_short_input_yields_no_frames():
    sr = 44100
    samples = sine(440.0, 0.01, sr)  # shorter than a single frame
    assert process_audio(samples, sr) == []
