import { describe, it, expect } from 'vitest';
import {
  frequencyToContinuousMidi,
  continuousMidiToFrequency,
  midiToNoteName,
  midiToPitchClass,
  midiToOctave,
  noteNameToMidi,
} from '../src/core/midi';

describe('midi conversions', () => {
  it('A4 = 440 Hz', () => {
    expect(frequencyToContinuousMidi(440)).toBeCloseTo(69, 6);
    expect(continuousMidiToFrequency(69)).toBeCloseTo(440, 6);
  });

  it('C4 -> MIDI 60 and C5 -> MIDI 72', () => {
    expect(noteNameToMidi('C4')).toBe(60);
    expect(noteNameToMidi('C5')).toBe(72);
    expect(midiToNoteName(60)).toBe('C4');
    expect(midiToNoteName(72)).toBe('C5');
  });

  it('distinguishes the same pitch class across octaves', () => {
    expect(midiToNoteName(60)).toBe('C4');
    expect(midiToNoteName(72)).toBe('C5');
    expect(midiToOctave(60)).toBe(4);
    expect(midiToOctave(72)).toBe(5);
  });

  it('handles sharps and flats in note names', () => {
    expect(noteNameToMidi('F#4')).toBe(66);
    expect(noteNameToMidi('Bb3')).toBe(58);
    expect(midiToNoteName(66)).toBe('F#4');
    expect(midiToPitchClass(66)).toBe(6);
  });

  it('returns null for invalid frequencies', () => {
    expect(frequencyToContinuousMidi(0)).toBeNull();
    expect(frequencyToContinuousMidi(-10)).toBeNull();
    expect(frequencyToContinuousMidi(NaN)).toBeNull();
    expect(frequencyToContinuousMidi(Infinity)).toBeNull();
  });

  it('returns null for invalid note names', () => {
    expect(noteNameToMidi('')).toBeNull();
    expect(noteNameToMidi('H4')).toBeNull();
    expect(noteNameToMidi('C')).toBeNull();
    expect(noteNameToMidi('not-a-note')).toBeNull();
  });

  it('frequency <-> midi round-trips', () => {
    expect(frequencyToContinuousMidi(continuousMidiToFrequency(60))).toBeCloseTo(60, 6);
    expect(frequencyToContinuousMidi(continuousMidiToFrequency(69.5))).toBeCloseTo(69.5, 6);
  });
});
