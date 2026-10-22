import { describe, it, expect } from 'vitest';
import { mapToSolfege, tonicPitchClass, scalePitchClasses, solfegeLabel } from '../src/core/solfege';

describe('solfege mapping', () => {
  it('C major: C=Do, E=Mi, A=La', () => {
    expect(mapToSolfege(60, 'C', 'major').solfege).toBe('Do');
    expect(mapToSolfege(64, 'C', 'major').solfege).toBe('Mi');
    expect(mapToSolfege(69, 'C', 'major').solfege).toBe('La');
  });

  it('E major: E=Do, G#=Mi, C#=La', () => {
    expect(mapToSolfege(64, 'E', 'major').solfege).toBe('Do');
    expect(mapToSolfege(68, 'E', 'major').solfege).toBe('Mi');
    expect(mapToSolfege(73, 'E', 'major').solfege).toBe('La');
  });

  it('changing key does not change MIDI pitch or note name', () => {
    const inC = mapToSolfege(60, 'C', 'major');
    const inG = mapToSolfege(60, 'G', 'major');
    expect(inC.noteMidi).toBe(60);
    expect(inC.noteName).toBe('C4');
    expect(inG.noteMidi).toBe(60);
    expect(inG.noteName).toBe('C4');
  });

  it('out-of-scale notes are marked, not forced onto a natural degree', () => {
    const m = mapToSolfege(66, 'C', 'major'); // F# in C major
    expect(m.inScale).toBe(false);
    expect(m.alteration).toBe('sharp');
    expect(m.solfege).toBe('Fa');
  });

  it('in-scale note reports its degree and solfege', () => {
    const m = mapToSolfege(67, 'C', 'major'); // G in C major
    expect(m.inScale).toBe(true);
    expect(m.scaleDegree).toBe(5);
    expect(m.solfege).toBe('Sol');
    expect(m.alteration).toBeNull();
  });

  it('resolves tonic pitch classes', () => {
    expect(tonicPitchClass('C')).toBe(0);
    expect(tonicPitchClass('G')).toBe(7);
    expect(tonicPitchClass('Bb')).toBe(10);
    expect(tonicPitchClass('E')).toBe(4);
    expect(tonicPitchClass('F#')).toBe(6);
  });

  it('builds C major scale pitch classes', () => {
    expect(scalePitchClasses(0, 'major')).toEqual([0, 2, 4, 5, 7, 9, 11]);
  });

  it('solfegeLabel formats in-scale and accidental notes', () => {
    expect(solfegeLabel(60, 'C', 'major')).toBe('Do');
    expect(solfegeLabel(66, 'C', 'major')).toBe('Fa♯'); // F# in C major
    expect(solfegeLabel(64, 'E', 'major')).toBe('Do'); // E is the tonic
  });
});
