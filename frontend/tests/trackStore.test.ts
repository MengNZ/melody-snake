import { describe, it, expect, beforeEach } from 'vitest';
import { MelodyTrackStore } from '../src/core/trackStore';

describe('MelodyTrackStore', () => {
  let store: MelodyTrackStore;

  beforeEach(() => {
    store = new MelodyTrackStore('file');
  });

  it('appends notes in order with stable ids and increasing indices', () => {
    const a = store.appendNote({ startTime: 0, endTime: 0.5, midiNote: 60, confidence: 0.9 });
    const b = store.appendNote({ startTime: 0.6, endTime: 1.0, midiNote: 64, confidence: 0.9 });
    expect(a.index).toBe(0);
    expect(b.index).toBe(1);
    expect(a.id).not.toBe(b.id);
    expect(store.noteCount).toBe(2);
  });

  it('never overwrites existing notes when appending', () => {
    store.appendNote({ startTime: 0, endTime: 0.5, midiNote: 60, confidence: 0.9 });
    const firstId = store.getSnapshot().track.notes[0].id;
    store.appendNote({ startTime: 0.6, endTime: 1.0, midiNote: 64, confidence: 0.9 });
    const snap = store.getSnapshot();
    expect(snap.track.notes[0].id).toBe(firstId);
    expect(snap.track.notes[0].midiNote).toBe(60);
    expect(snap.track.notes).toHaveLength(2);
  });

  it('editNote records correction history and recomputes the note name', () => {
    const n = store.appendNote({ startTime: 0, endTime: 0.5, midiNote: 60, confidence: 0.9 });
    store.editNote(n.id, 61);
    const updated = store.getSnapshot().track.notes[0];
    expect(updated.midiNote).toBe(61);
    expect(updated.noteName).toBe('C#4');
    expect(updated.status).toBe('corrected');
    expect(updated.source).toBe('manual');
    expect(updated.originalMidiNote).toBe(60);
    expect(updated.correctionHistory).toHaveLength(1);
  });

  it('undo reverts a manual correction', () => {
    const n = store.appendNote({ startTime: 0, endTime: 0.5, midiNote: 60, confidence: 0.9 });
    store.editNote(n.id, 61);
    expect(store.undo()).toBe(true);
    const reverted = store.getSnapshot().track.notes[0];
    expect(reverted.midiNote).toBe(60);
    expect(reverted.status).toBe('confirmed');
    expect(reverted.source).toBe('auto');
  });

  it('undo returns false when there is nothing to undo', () => {
    expect(store.undo()).toBe(false);
  });

  it('newTrack isolates the old track from the new one', () => {
    store.appendNote({ startTime: 0, endTime: 0.5, midiNote: 60, confidence: 0.9 });
    store.newTrack('file');
    expect(store.noteCount).toBe(0);
    store.appendNote({ startTime: 0, endTime: 0.5, midiNote: 62, confidence: 0.9 });
    expect(store.noteCount).toBe(1);
    expect(store.getSnapshot().track.notes[0].midiNote).toBe(62);
  });

  it('editing an unknown id returns null and does not mutate', () => {
    expect(store.editNote('nope', 60)).toBeNull();
    expect(store.noteCount).toBe(0);
  });
});

describe('computeIntervals (via store snapshot)', () => {
  it('computes intervals for adjacent notes in track order', () => {
    const store = new MelodyTrackStore('file');
    store.appendNote({ startTime: 0, endTime: 0.5, midiNote: 60, confidence: 0.9 });
    store.appendNote({ startTime: 0.6, endTime: 1.0, midiNote: 64, confidence: 0.9 });
    store.appendNote({ startTime: 1.1, endTime: 1.5, midiNote: 62, confidence: 0.9 });
    store.appendNote({ startTime: 1.6, endTime: 2.0, midiNote: 67, confidence: 0.9 });
    const intervals = store.getSnapshot().intervals;
    expect(intervals).toHaveLength(3);
    expect(intervals[0].intervalName).toBe('大三度');
    expect(intervals[1].intervalName).toBe('大二度');
    expect(intervals[1].direction).toBe('down');
    expect(intervals[2].intervalName).toBe('纯四度');
  });

  it('recomputes intervals after a manual edit', () => {
    const store = new MelodyTrackStore('file');
    store.appendNote({ startTime: 0, endTime: 0.5, midiNote: 60, confidence: 0.9 });
    const b = store.appendNote({ startTime: 0.6, endTime: 1.0, midiNote: 64, confidence: 0.9 });
    expect(store.getSnapshot().intervals[0].intervalName).toBe('大三度');
    store.editNote(b.id, 67); // E4 -> G4
    expect(store.getSnapshot().intervals[0].intervalName).toBe('纯五度');
  });
});
