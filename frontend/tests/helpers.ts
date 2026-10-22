import type { PitchEstimate } from '../src/core/types';
import { NoteEventDetector } from '../src/core/segmentation';

/** Build a single synthetic pitch frame (timestamp in seconds). */
export function pitchFrame(timestamp: number, roundedMidi: number | null, confidence = 0.9): PitchEstimate {
  const voiced = roundedMidi != null;
  return {
    timestamp,
    frequencyHz: null,
    continuousMidi: roundedMidi,
    roundedMidi,
    confidence: voiced ? confidence : 0,
    voiced,
    algorithm: 'test',
    diagnostics: {},
  };
}

/**
 * Build a frame stream from a note list. Each note is either a MIDI number
 * (voiced) or null (silence), held for durationMs at the given hop size.
 */
export function noteSequence(
  notes: Array<{ midi: number | null; durationMs: number }>,
  hopMs = 10,
): PitchEstimate[] {
  const frames: PitchEstimate[] = [];
  let tMs = 0;
  for (const { midi, durationMs } of notes) {
    const count = Math.max(1, Math.round(durationMs / hopMs));
    for (let i = 0; i < count; i++) {
      frames.push(pitchFrame(tMs / 1000, midi));
      tMs += hopMs;
    }
  }
  return frames;
}

/** Run a detector over a stream and collect only committed note events. */
export function runDetector(frames: PitchEstimate[]): Array<{ midiNote: number; startTime: number; endTime: number }> {
  const d = new NoteEventDetector();
  const events: Array<{ midiNote: number; startTime: number; endTime: number }> = [];
  for (const f of frames) {
    for (const out of d.process(f)) {
      if (out.type === 'commit') events.push(out.event);
    }
  }
  for (const out of d.flush()) {
    if (out.type === 'commit') events.push(out.event);
  }
  return events;
}
