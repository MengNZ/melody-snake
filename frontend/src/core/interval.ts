// Interval calculation between two adjacent *confirmed* notes.
// Works on MIDI numbers, never on raw pitch-estimate frames.

import type { Direction, IntervalQuality } from './types';

export interface IntervalResult {
  deltaSemitones: number;
  direction: Direction;
  intervalNumber: number;
  intervalQuality: IntervalQuality;
  intervalName: string;
  octaveDisplacement: number;
  compound: boolean;
}

const SIMPLE_INTERVALS: Record<number, { number: number; quality: Exclude<IntervalQuality, 'd'> }> = {
  0: { number: 1, quality: 'P' },
  1: { number: 2, quality: 'm' },
  2: { number: 2, quality: 'M' },
  3: { number: 3, quality: 'm' },
  4: { number: 3, quality: 'M' },
  5: { number: 4, quality: 'P' },
  6: { number: 4, quality: 'A' },
  7: { number: 5, quality: 'P' },
  8: { number: 6, quality: 'm' },
  9: { number: 6, quality: 'M' },
  10: { number: 7, quality: 'm' },
  11: { number: 7, quality: 'M' },
};

const CN_NUM: Record<number, string> = { 1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '七', 8: '八' };
const QUALITY_CN: Record<string, string> = { P: '纯', M: '大', m: '小', A: '增', d: '减' };

function buildName(number: number, quality: string): string {
  return `${QUALITY_CN[quality] ?? ''}${CN_NUM[number] ?? number}度`;
}

/** Compute the interval from previousMidi to currentMidi. */
export function computeInterval(previousMidi: number, currentMidi: number): IntervalResult {
  const delta = currentMidi - previousMidi;
  const direction: Direction = delta > 0 ? 'up' : delta < 0 ? 'down' : 'unison';
  const absDelta = Math.abs(delta);
  const octaveDisplacement = Math.floor(absDelta / 12);
  const semis = absDelta % 12;

  if (semis === 0) {
    if (absDelta === 0) {
      return {
        deltaSemitones: 0,
        direction: 'unison',
        intervalNumber: 1,
        intervalQuality: 'P',
        intervalName: '纯一度',
        octaveDisplacement: 0,
        compound: false,
      };
    }
    return {
      deltaSemitones: delta,
      direction,
      intervalNumber: 8,
      intervalQuality: 'P',
      intervalName: '纯八度',
      octaveDisplacement,
      compound: true,
    };
  }

  const simple = SIMPLE_INTERVALS[semis];
  return {
    deltaSemitones: delta,
    direction,
    intervalNumber: simple.number,
    intervalQuality: simple.quality,
    intervalName: buildName(simple.number, simple.quality),
    octaveDisplacement,
    compound: absDelta > 12,
  };
}
