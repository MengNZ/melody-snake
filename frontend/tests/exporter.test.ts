import { describe, it, expect } from 'vitest';
import { MelodyTrackStore } from '../src/core/trackStore';
import { trackToCSV, trackToJSON } from '../src/core/exporter';

describe('exporter', () => {
  it('exports JSON that round-trips', () => {
    const store = new MelodyTrackStore('file');
    store.appendNote({ startTime: 0, endTime: 0.5, midiNote: 60, confidence: 0.9 });
    store.appendNote({ startTime: 0.6, endTime: 1.0, midiNote: 64, confidence: 0.9 });
    const snap = store.getSnapshot();
    const parsed = JSON.parse(trackToJSON(snap.track, snap.intervals));
    expect(parsed.track.notes).toHaveLength(2);
    expect(parsed.intervals[0].intervalName).toBe('大三度');
  });

  it('exports CSV that can be parsed', () => {
    const store = new MelodyTrackStore('file');
    store.appendNote({ startTime: 0, endTime: 0.5, midiNote: 60, confidence: 0.9 });
    store.appendNote({ startTime: 0.6, endTime: 1.0, midiNote: 64, confidence: 0.9 });
    const snap = store.getSnapshot();
    const lines = trackToCSV(snap.track, snap.intervals).split('\n');
    expect(lines[0]).toContain('noteName');
    expect(lines).toHaveLength(3); // header + 2 notes
    expect(lines[1].split(',')[1]).toBe('C4');
    expect(lines[2].split(',')[1]).toBe('E4');
  });
});
