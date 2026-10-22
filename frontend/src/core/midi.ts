// MIDI <-> frequency <-> note name conversions (pure, no I/O).

export const A4_MIDI = 69;
export const A4_FREQUENCY_HZ = 440;

const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'] as const;

const LETTER_TO_PC: Record<string, number> = {
  C: 0,
  D: 2,
  E: 4,
  F: 5,
  G: 7,
  A: 9,
  B: 11,
};

/** m = 69 + 12 * log2(f / 440). Returns null for invalid/zero/negative/NaN. */
export function frequencyToContinuousMidi(frequencyHz: number): number | null {
  if (!Number.isFinite(frequencyHz) || frequencyHz <= 0) return null;
  return A4_MIDI + 12 * Math.log2(frequencyHz / A4_FREQUENCY_HZ);
}

/** f = 440 * 2^((m - 69) / 12). */
export function continuousMidiToFrequency(midi: number): number {
  return A4_FREQUENCY_HZ * Math.pow(2, (midi - A4_MIDI) / 12);
}

/** 60 -> "C4", 61 -> "C#4", 69 -> "A4", 72 -> "C5". */
export function midiToNoteName(midi: number): string {
  const rounded = Math.round(midi);
  const pitchClass = ((rounded % 12) + 12) % 12;
  const octave = Math.floor(rounded / 12) - 1;
  return `${NOTE_NAMES[pitchClass]}${octave}`;
}

/** Pitch class (0=C, 1=C#, ..., 11=B), always in [0, 12). */
export function midiToPitchClass(midi: number): number {
  return ((Math.round(midi) % 12) + 12) % 12;
}

/** Octave number, e.g. 60 -> 4, 72 -> 5. */
export function midiToOctave(midi: number): number {
  return Math.floor(Math.round(midi) / 12) - 1;
}

/**
 * Parse a note name like "C4", "F#4", "Bb3" into a MIDI number.
 * Round-trips with midiToNoteName for sharp spellings. Returns null on bad input.
 */
export function noteNameToMidi(noteName: string): number | null {
  const m = /^([A-Ga-g])([#b]?)(-?\d+)$/.exec(noteName.trim());
  if (!m) return null;
  const base = LETTER_TO_PC[m[1].toUpperCase()];
  if (base === undefined) return null;
  const accidental = m[2];
  const octave = parseInt(m[3], 10);
  const semitone = base + (accidental === '#' ? 1 : accidental === 'b' ? -1 : 0);
  return (octave + 1) * 12 + semitone;
}
