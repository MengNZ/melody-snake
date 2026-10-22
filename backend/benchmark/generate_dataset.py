"""Generate the benchmark dataset with exactly-known ground truth.

Cases (per the v2 spec):
  A  clear single note
  B  piano / guitar-like single melody (SYNTHETIC, not a real recording)
  C  fast consecutive notes
  D  glissando / vibrato / decay / repeated note
  E  full mix (melody + accompaniment + percussion) — stress test, not expected to pass

Every reference annotation is derived from the SAME synthesis parameters used to
produce the audio. Real guitar/piano/full-song recordings are NOT synthesized
here; see the report for how to add them.
"""

import json
from pathlib import Path

import numpy as np

from melody_snake.theory.midi import continuous_midi_to_frequency as midi_freq

from . import synth

SR = 44100


def _note_segments(midis, note_dur=0.4, gap=0.1, tone=synth.piano_like, **kw):
    segs = []
    ref = []
    t = 0.0
    for i, m in enumerate(midis):
        segs.append(tone(midi_freq(m), note_dur, SR, **kw))
        ref.append({"midi": m, "start": round(t, 3), "end": round(t + note_dur, 3)})
        t += note_dur
        if gap:
            segs.append(synth.silence(gap, SR))
            t += gap
    return segs, ref


def build_dataset(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = []

    def add(name, samples, ref, desc):
        wav = out / f"{name}.wav"
        refp = out / f"{name}.ref.json"
        synth.write_wav(wav, samples, SR)
        refp.write_text(json.dumps(ref, ensure_ascii=False), encoding="utf-8")
        manifest.append({"name": name, "desc": desc, "wav": str(wav), "ref": str(refp)})

    # A — clear single note
    add("A_single_note", synth.sine(midi_freq(69), 1.0, SR),
        [{"midi": 69, "start": 0.0, "end": 1.0}], "440Hz sine, 1s")

    # B — piano-like and guitar-like melody
    midis = [60, 64, 62, 67]
    segs, ref = _note_segments(midis, tone=synth.piano_like)
    add("B_piano_melody", synth.concat(segs, SR), ref, "synthetic piano-like C4-E4-D4-G4")

    segs, ref = _note_segments(midis, tone=synth.guitar_like, seed=0)
    add("B_guitar_melody", synth.concat(segs, SR), ref, "synthetic Karplus-Strong guitar C4-E4-D4-G4")

    # C — fast consecutive notes (8 notes, 80ms each, no gap)
    fast = [60, 62, 64, 65, 67, 69, 71, 72]
    segs = [synth.sine(midi_freq(m), 0.08, SR) for m in fast]
    ref = [{"midi": m, "start": round(i * 0.08, 3), "end": round((i + 1) * 0.08, 3)} for i, m in enumerate(fast)]
    add("C_fast_notes", synth.concat(segs, SR), ref, "8 sine notes, 80ms each")

    # D — vibrato (should be 1 note)
    add("D_vibrato", synth.vibrato(midi_freq(69), 1.0, SR),
        [{"midi": 69, "start": 0.0, "end": 1.0}], "440Hz +-0.5sem vibrato, 5Hz")

    # D — glissando: hold C4, glide to E4, hold E4
    segs = [synth.sine(midi_freq(60), 0.5, SR), synth.glide(midi_freq(60), midi_freq(64), 0.1, SR),
            synth.sine(midi_freq(64), 0.4, SR)]
    add("D_glissando", synth.concat(segs, SR),
        [{"midi": 60, "start": 0.0, "end": 0.5}, {"midi": 64, "start": 0.6, "end": 1.0}],
        "hold C4 0.5s, glide to E4 0.1s, hold E4 0.4s")

    # D — decay (piano-like, note fades below voicing threshold)
    add("D_decay", synth.piano_like(midi_freq(60), 1.5, SR),
        [{"midi": 60, "start": 0.0, "end": 1.2}], "piano-like C4 with decay")

    # D — repeated same note with a gap
    segs = [synth.sine(midi_freq(60), 0.4, SR), synth.silence(0.1, SR), synth.sine(midi_freq(60), 0.4, SR)]
    add("D_repeat", synth.concat(segs, SR),
        [{"midi": 60, "start": 0.0, "end": 0.4}, {"midi": 60, "start": 0.5, "end": 0.9}],
        "C4, gap, C4")

    # E — full mix (stress test)
    melody = [60, 64, 62, 67]
    total = 1.9
    t_axis = np.arange(int(total * SR), dtype=np.float64) / SR
    mix = np.zeros_like(t_axis)
    for i, m in enumerate(melody):
        start = i * 0.5
        seg = synth.piano_like(midi_freq(m), 0.4, SR, amp=0.4)
        s = int(start * SR)
        mix[s:s + len(seg)] += seg
    for m in [48, 52, 55]:  # C3 E3 G3 chord pad
        mix += 0.08 * synth.sine(midi_freq(m), total, SR)
    for start in [0.0, 0.5, 1.0, 1.5]:  # bass C2
        seg = synth.sine(midi_freq(36), 0.3, SR, amp=0.15)
        s = int(start * SR)
        mix[s:s + len(seg)] += seg
    rng = np.random.default_rng(0)
    for start in np.arange(0.0, total, 0.25):  # percussion noise bursts
        s = int(start * SR)
        e = s + int(0.03 * SR)
        mix[s:e] += 0.12 * rng.standard_normal(e - s)
    mix = mix / max(np.max(np.abs(mix)), 1e-6) * 0.8
    ref = [{"midi": m, "start": round(i * 0.5, 3), "end": round(i * 0.5 + 0.4, 3)} for i, m in enumerate(melody)]
    add("E_mix", mix, ref, "melody + chord pad + bass + percussion (stress)")

    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    import sys
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "benchmark_data"
    m = build_dataset(target)
    print(f"generated {len(m)} samples into {target}")
    for x in m:
        print(" -", x["name"], "::", x["desc"])
