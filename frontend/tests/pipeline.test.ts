import { describe, it, expect } from 'vitest';
import { MelodyEngine } from '../src/core/pipeline';
import { noteSequence } from './helpers';

describe('MelodyEngine (detector + track store)', () => {
  it('C4 -> E4 -> D4 -> G4 yields ordered events, intervals and solfege', () => {
    const engine = new MelodyEngine(undefined, 'file');
    engine.processAll(
      noteSequence(
        [
          { midi: 60, durationMs: 400 },
          { midi: 64, durationMs: 400 },
          { midi: 62, durationMs: 400 },
          { midi: 67, durationMs: 400 },
        ],
        10,
      ),
    );
    engine.flush();

    const snap = engine.snapshot();
    const notes = snap.track.track.notes;
    const intervals = snap.track.intervals;

    expect(notes.map((n) => n.midiNote)).toEqual([60, 64, 62, 67]);
    expect(notes.map((n) => n.index)).toEqual([0, 1, 2, 3]);
    expect(intervals).toHaveLength(3);
    expect(intervals[0].intervalName).toBe('大三度');
    expect(intervals[1].intervalName).toBe('大二度');
    expect(intervals[1].direction).toBe('down');
    expect(intervals[2].intervalName).toBe('纯四度');

    for (let i = 1; i < notes.length; i++) {
      expect(notes[i].startTime).toBeGreaterThanOrEqual(notes[i - 1].endTime);
    }
  });

  it('history is preserved and a new track does not pollute the old', () => {
    const engine = new MelodyEngine(undefined, 'file');
    engine.processAll(
      noteSequence(
        [
          { midi: 60, durationMs: 400 },
          { midi: 64, durationMs: 400 },
        ],
        10,
      ),
    );
    engine.flush();
    expect(engine.snapshot().track.track.notes.map((n) => n.midiNote)).toEqual([60, 64]);

    engine.store.newTrack('file');
    expect(engine.snapshot().track.track.notes).toHaveLength(0);
  });

  it('flush (pause) commits an in-flight note', () => {
    const engine = new MelodyEngine(undefined, 'file');
    engine.processAll(noteSequence([{ midi: 60, durationMs: 300 }], 10));
    engine.flush();
    expect(engine.snapshot().track.track.notes.map((n) => n.midiNote)).toEqual([60]);
  });
});
