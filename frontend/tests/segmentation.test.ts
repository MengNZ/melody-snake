import { describe, it, expect } from 'vitest';
import { NoteEventDetector } from '../src/core/segmentation';
import { noteSequence, pitchFrame, runDetector } from './helpers';

describe('NoteEventDetector', () => {
  it('a long stable note produces exactly one event', () => {
    const frames = noteSequence([{ midi: 60, durationMs: 1000 }], 10);
    const events = runDetector(frames);
    expect(events).toHaveLength(1);
    expect(events[0].midiNote).toBe(60);
  });

  it('a single-frame outlier does not create a new note', () => {
    const d = new NoteEventDetector();
    const events: number[] = [];
    let tMs = 0;
    const feed = (midi: number | null) => {
      for (const out of d.process(pitchFrame(tMs / 1000, midi))) {
        if (out.type === 'commit') events.push(out.event.midiNote);
      }
      tMs += 10;
    };
    for (let i = 0; i < 30; i++) feed(60); // 300ms C4
    feed(64); // outlier
    for (let i = 0; i < 30; i++) feed(60); // 300ms C4
    for (const out of d.flush()) if (out.type === 'commit') events.push(out.event.midiNote);
    expect(events).toEqual([60]);
  });

  it('a stable pitch change produces a new event', () => {
    const frames = noteSequence(
      [
        { midi: 60, durationMs: 300 },
        { midi: 64, durationMs: 300 },
      ],
      10,
    );
    const events = runDetector(frames);
    expect(events.map((e) => e.midiNote)).toEqual([60, 64]);
    expect(events[1].startTime).toBeGreaterThanOrEqual(events[0].endTime);
  });

  it('silence is never detected as a note', () => {
    const frames = noteSequence([{ midi: null, durationMs: 500 }], 10);
    expect(runDetector(frames)).toHaveLength(0);
  });

  it('fast notes are not all swallowed by the minimum-duration rule', () => {
    const frames = noteSequence(
      [
        { midi: 60, durationMs: 60 },
        { midi: 62, durationMs: 60 },
        { midi: 64, durationMs: 60 },
        { midi: 65, durationMs: 60 },
        { midi: 67, durationMs: 60 },
      ],
      10,
    );
    const events = runDetector(frames);
    expect(events.map((e) => e.midiNote)).toEqual([60, 62, 64, 65, 67]);
  });

  it('same pitch re-articulated across a silence gap becomes two events', () => {
    const frames = noteSequence(
      [
        { midi: 60, durationMs: 200 },
        { midi: null, durationMs: 100 },
        { midi: 60, durationMs: 200 },
      ],
      10,
    );
    const events = runDetector(frames);
    expect(events.map((e) => e.midiNote)).toEqual([60, 60]);
  });

  it('vibrato within tolerance does not split a note', () => {
    const d = new NoteEventDetector();
    const events: number[] = [];
    let tMs = 0;
    for (let i = 0; i < 100; i++) {
      const midi = i % 2 === 0 ? 60 : 60.4; // ±0.4 semitone, within 0.7 tolerance
      for (const out of d.process(pitchFrame(tMs / 1000, midi))) {
        if (out.type === 'commit') events.push(out.event.midiNote);
      }
      tMs += 10;
    }
    for (const out of d.flush()) if (out.type === 'commit') events.push(out.event.midiNote);
    expect(events).toHaveLength(1);
  });

  it('a slow continuous glissando is not split into many notes', () => {
    const d = new NoteEventDetector();
    const events: number[] = [];
    let tMs = 0;
    for (let i = 0; i < 100; i++) {
      const midi = 60 + (6 * i) / 99; // glide 60 -> 66 over 1s
      for (const out of d.process(pitchFrame(tMs / 1000, midi))) {
        if (out.type === 'commit') events.push(out.event.midiNote);
      }
      tMs += 10;
    }
    for (const out of d.flush()) if (out.type === 'commit') events.push(out.event.midiNote);
    expect(events.length).toBeLessThan(3);
  });

  it('a FAST glide does not split into spurious intermediate notes', () => {
    // Regression: a 4-semitone glide over ~160ms used to be committed as a
    // series of intermediate notes (61, 62, 63). With continuous-midi stability
    // checking it must settle into at most the start and the settled pitch.
    const d = new NoteEventDetector();
    const events: number[] = [];
    let tMs = 0;
    for (let i = 0; i < 16; i++) {
      const midi = 60 + (4 * i) / 15; // glide 60 -> 64
      for (const out of d.process(pitchFrame(tMs / 1000, midi))) {
        if (out.type === 'commit') events.push(out.event.midiNote);
      }
      tMs += 10;
    }
    for (let i = 0; i < 20; i++) {
      for (const out of d.process(pitchFrame(tMs / 1000, 64))) {
        if (out.type === 'commit') events.push(out.event.midiNote);
      }
      tMs += 10;
    }
    for (const out of d.flush()) if (out.type === 'commit') events.push(out.event.midiNote);
    expect(events.length).toBeLessThanOrEqual(2);
    expect(events[events.length - 1]).toBe(64);
  });
});
