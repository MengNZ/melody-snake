// MelodyTrackStore — the immutable, ordered history of confirmed notes.
// Invariant: notes are only ever APPENDED. Existing notes can change only via
// explicit editNote() (which records correctionHistory) or undo().

import type { IntervalEvent, MelodyTrack, NoteEvent, SourceType } from './types';
import { computeInterval } from './interval';
import { midiToNoteName } from './midi';

export interface TrackSnapshot {
  track: MelodyTrack;
  intervals: IntervalEvent[];
}

export interface AppendNoteInput {
  startTime: number;
  endTime: number;
  midiNote: number;
  frequencyHz?: number | null;
  confidence: number;
  status?: NoteEvent['status'];
  source?: NoteEvent['source'];
}

let idCounter = 0;

function nextId(): string {
  idCounter += 1;
  return `note-${idCounter}`;
}

export class MelodyTrackStore {
  private track: MelodyTrack;
  private undoStack: Array<{ noteId: string; from: number; to: number }> = [];

  constructor(sourceType: SourceType = 'file') {
    this.track = this.createTrack(sourceType);
  }

  private createTrack(sourceType: SourceType): MelodyTrack {
    return {
      trackId: `track-${Date.now()}-${Math.floor(Math.random() * 1e6)}`,
      createdAt: new Date().toISOString(),
      sourceType,
      selectedKey: 'C',
      notes: [],
      processingConfig: { sampleRate: 44100, frameSize: 2048, hopSize: 512 },
      revision: 0,
    };
  }

  get selectedKey(): string {
    return this.track.selectedKey;
  }

  get noteCount(): number {
    return this.track.notes.length;
  }

  setSelectedKey(key: string): void {
    this.track.selectedKey = key;
    this.track.revision += 1;
  }

  /** Append a confirmed note. Always appends to the tail; never overwrites. */
  appendNote(input: AppendNoteInput): NoteEvent {
    const note: NoteEvent = {
      id: nextId(),
      index: this.track.notes.length,
      startTime: input.startTime,
      endTime: input.endTime,
      midiNote: input.midiNote,
      noteName: midiToNoteName(input.midiNote),
      frequencyHz: input.frequencyHz ?? null,
      confidence: input.confidence,
      status: input.status ?? 'confirmed',
      source: input.source ?? 'auto',
      originalMidiNote: null,
      correctionHistory: [],
    };
    this.track.notes.push(note);
    this.track.revision += 1;
    return note;
  }

  /** Explicit user correction. Records history; returns null if id unknown. */
  editNote(id: string, newMidi: number): NoteEvent | null {
    const note = this.track.notes.find((n) => n.id === id);
    if (!note) return null;
    const from = note.midiNote;
    if (from === newMidi) return note;

    note.originalMidiNote = note.originalMidiNote ?? from;
    note.correctionHistory.push({ from, to: newMidi, at: new Date().toISOString() });
    note.midiNote = newMidi;
    note.noteName = midiToNoteName(newMidi);
    note.status = 'corrected';
    note.source = 'manual';

    this.undoStack.push({ noteId: id, from, to: newMidi });
    this.track.revision += 1;
    return note;
  }

  /** Undo the last manual correction. Returns false when there is nothing to undo. */
  undo(): boolean {
    const op = this.undoStack.pop();
    if (!op) return false;
    const note = this.track.notes.find((n) => n.id === op.noteId);
    if (!note) return false;

    note.midiNote = op.from;
    note.noteName = midiToNoteName(op.from);
    note.correctionHistory.pop();
    if (note.correctionHistory.length === 0) {
      note.status = 'confirmed';
      note.source = 'auto';
      note.originalMidiNote = null;
    }
    this.track.revision += 1;
    return true;
  }

  /** Reset to a brand-new empty track; the old track is not reused. */
  newTrack(sourceType: SourceType = 'file'): void {
    this.track = this.createTrack(sourceType);
    this.undoStack = [];
  }

  getSnapshot(): TrackSnapshot {
    return {
      track: { ...this.track, notes: [...this.track.notes] },
      intervals: computeIntervals(this.track.notes),
    };
  }
}

/** Derive interval events from adjacent confirmed notes (in track order). */
export function computeIntervals(notes: NoteEvent[]): IntervalEvent[] {
  const intervals: IntervalEvent[] = [];
  for (let i = 1; i < notes.length; i++) {
    const prev = notes[i - 1];
    const curr = notes[i];
    const r = computeInterval(prev.midiNote, curr.midiNote);
    intervals.push({
      previousNoteId: prev.id,
      currentNoteId: curr.id,
      deltaSemitones: r.deltaSemitones,
      direction: r.direction,
      intervalNumber: r.intervalNumber,
      intervalQuality: r.intervalQuality,
      intervalName: r.intervalName,
      octaveDisplacement: r.octaveDisplacement,
    });
  }
  return intervals;
}
