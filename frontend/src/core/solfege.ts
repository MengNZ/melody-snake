// Key <-> solfege mapping. Purely an *interpretation* of pitch: it never
// modifies the underlying MIDI note, only explains it within a chosen key.

import type { KeyMapping, ScaleType } from './types';
import { midiToNoteName, midiToPitchClass } from './midi';

const SCALE_PATTERNS: Record<ScaleType, number[]> = {
  major: [0, 2, 4, 5, 7, 9, 11],
  minor: [0, 2, 3, 5, 7, 8, 10], // natural minor
};

const SOLFEGE = ['Do', 'Re', 'Mi', 'Fa', 'Sol', 'La', 'Si'];

const LETTER_TO_PC: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

/** Supported major keys (v1) plus minor keys, keyed by tonic letter/accidental. */
export const SUPPORTED_MAJOR_KEYS = ['C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#', 'F', 'Bb', 'Eb', 'Ab', 'Db', 'Gb'] as const;

/** Resolve a key signature ("C", "F#", "Bb", ...) to its tonic pitch class. */
export function tonicPitchClass(keyName: string): number | null {
  const m = /^([A-Ga-g])([#b]?)$/.exec(keyName.trim());
  if (!m) return null;
  const base = LETTER_TO_PC[m[1].toUpperCase()];
  if (base === undefined) return null;
  const accidental = m[2];
  return (base + (accidental === '#' ? 1 : accidental === 'b' ? -1 : 0) + 12) % 12;
}

/** The seven scale pitch classes (in ascending degree order) for a tonic+mode. */
export function scalePitchClasses(tonic: number, scaleType: ScaleType): number[] {
  return SCALE_PATTERNS[scaleType].map((s) => (tonic + s) % 12);
}

/**
 * Map a MIDI note to its solfege within a key. Out-of-scale notes are reported
 * as the nearest degree with an explicit sharp/flat alteration (never silently
 * forced onto a natural scale degree).
 */
export function mapToSolfege(noteMidi: number, keySignature: string, scaleType: ScaleType): KeyMapping {
  const tonic = tonicPitchClass(keySignature);
  if (tonic === null) {
    throw new Error(`Unsupported key signature: ${keySignature}`);
  }

  const pc = midiToPitchClass(noteMidi);
  const scale = scalePitchClasses(tonic, scaleType);
  const idx = scale.indexOf(pc);

  const base: KeyMapping = {
    keySignature,
    scaleType,
    noteMidi,
    noteName: midiToNoteName(noteMidi),
    scaleDegree: null,
    solfege: '',
    inScale: false,
    alteration: null,
  };

  if (idx >= 0) {
    return { ...base, scaleDegree: idx + 1, solfege: SOLFEGE[idx], inScale: true };
  }

  for (let i = 0; i < scale.length; i++) {
    if ((scale[i] + 1) % 12 === pc) {
      return { ...base, scaleDegree: i + 1, solfege: SOLFEGE[i], alteration: 'sharp', inScale: false };
    }
    if ((scale[i] + 11) % 12 === pc) {
      return { ...base, scaleDegree: i + 1, solfege: SOLFEGE[i], alteration: 'flat', inScale: false };
    }
  }

  return base;
}

/** Display label: "Sol", or "Fa♯" / "Si♭" for out-of-scale accidentals. */
export function solfegeLabel(noteMidi: number, keySignature: string, scaleType: ScaleType = 'major'): string {
  const m = mapToSolfege(noteMidi, keySignature, scaleType);
  if (m.inScale) return m.solfege;
  return m.solfege + (m.alteration === 'sharp' ? '♯' : m.alteration === 'flat' ? '♭' : '');
}
