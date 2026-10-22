import { describe, it, expect } from 'vitest';
import { computeInterval } from '../src/core/interval';

describe('interval calculation', () => {
  it('C4 -> E4 = +4 semitones, ascending major third', () => {
    const r = computeInterval(60, 64);
    expect(r.deltaSemitones).toBe(4);
    expect(r.direction).toBe('up');
    expect(r.intervalNumber).toBe(3);
    expect(r.intervalQuality).toBe('M');
    expect(r.intervalName).toBe('大三度');
  });

  it('E4 -> D4 = -2 semitones, descending major second', () => {
    const r = computeInterval(64, 62);
    expect(r.deltaSemitones).toBe(-2);
    expect(r.direction).toBe('down');
    expect(r.intervalName).toBe('大二度');
  });

  it('C4 -> G4 = +7 semitones, perfect fifth', () => {
    const r = computeInterval(60, 67);
    expect(r.deltaSemitones).toBe(7);
    expect(r.direction).toBe('up');
    expect(r.intervalQuality).toBe('P');
    expect(r.intervalName).toBe('纯五度');
  });

  it('G4 -> C4 = -7 semitones, descending perfect fifth', () => {
    const r = computeInterval(67, 60);
    expect(r.deltaSemitones).toBe(-7);
    expect(r.direction).toBe('down');
    expect(r.intervalName).toBe('纯五度');
  });

  it('C4 -> C5 = +12 semitones, perfect octave', () => {
    const r = computeInterval(60, 72);
    expect(r.deltaSemitones).toBe(12);
    expect(r.intervalNumber).toBe(8);
    expect(r.intervalName).toBe('纯八度');
    expect(r.octaveDisplacement).toBe(1);
    expect(r.compound).toBe(true);
  });

  it('unison (identical pitch)', () => {
    const r = computeInterval(60, 60);
    expect(r.deltaSemitones).toBe(0);
    expect(r.direction).toBe('unison');
    expect(r.intervalName).toBe('纯一度');
  });

  it('minor / major qualities across several intervals', () => {
    expect(computeInterval(60, 61).intervalName).toBe('小二度'); // C -> C#
    expect(computeInterval(60, 63).intervalName).toBe('小三度'); // C -> Eb
    expect(computeInterval(60, 68).intervalName).toBe('小六度'); // C -> Ab
    expect(computeInterval(60, 71).intervalName).toBe('大七度'); // C -> B
  });
});
