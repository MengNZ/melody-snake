"""Full-pipeline regression tests (audio -> YIN -> segmentation -> metrics).

These reproduce the two bugs found during benchmarking:
  1. fast consecutive notes were swallowed (recall ~0.38)
  2. a fast glide was split into spurious intermediate notes (precision ~0.67)

They require the bundled segmentation CLI (dist/segment-cli.mjs); skipped if not
built. Build it with: cd frontend && node scripts/build-segment-cli.mjs
"""

import json
from pathlib import Path

import pytest

from benchmark import synth
from benchmark.benchmark import DEFAULT_SEGMENT_CLI, benchmark_sample
from melody_snake.theory.midi import continuous_midi_to_frequency as mf

SR = 44100

pytestmark = pytest.mark.skipif(
    not Path(DEFAULT_SEGMENT_CLI).exists(),
    reason="segment-cli not built; run `cd frontend && node scripts/build-segment-cli.mjs`",
)


def _write(tmp_path, name, samples, ref):
    wav = tmp_path / f"{name}.wav"
    refp = tmp_path / f"{name}.ref.json"
    synth.write_wav(wav, samples, SR)
    refp.write_text(json.dumps(ref), encoding="utf-8")
    return wav, refp


def test_single_note(tmp_path):
    wav, refp = _write(tmp_path, "a4", synth.sine(mf(69), 1.0, SR), [{"midi": 69, "start": 0.0, "end": 1.0}])
    metrics, notes, _ = benchmark_sample(wav, refp)
    assert metrics["note_precision"] == 1.0
    assert metrics["note_recall"] == 1.0
    assert metrics["octave_errors"] == 0
    assert notes[0]["midiNote"] == 69


def test_fast_notes_not_swallowed(tmp_path):
    fast = [60, 62, 64, 65, 67, 69, 71, 72]
    segs = [synth.sine(mf(m), 0.08, SR) for m in fast]
    ref = [{"midi": m, "start": round(i * 0.08, 3), "end": round((i + 1) * 0.08, 3)} for i, m in enumerate(fast)]
    wav, refp = _write(tmp_path, "fast", synth.concat(segs, SR), ref)
    metrics, notes, _ = benchmark_sample(wav, refp)
    assert metrics["note_recall"] >= 0.75, metrics


def test_fast_glide_no_spurious_notes(tmp_path):
    segs = [synth.sine(mf(60), 0.5, SR), synth.glide(mf(60), mf(64), 0.1, SR), synth.sine(mf(64), 0.4, SR)]
    ref = [{"midi": 60, "start": 0.0, "end": 0.5}, {"midi": 64, "start": 0.6, "end": 1.0}]
    wav, refp = _write(tmp_path, "gliss", synth.concat(segs, SR), ref)
    metrics, notes, _ = benchmark_sample(wav, refp)
    assert metrics["note_precision"] >= 0.9, metrics
