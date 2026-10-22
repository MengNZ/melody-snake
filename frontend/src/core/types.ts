// Core data model — single source of truth for the interpretation layer.
// The Python backend emits PitchEstimate frames over WebSocket with the SAME
// JSON shape defined here. Everything downstream (segmentation, track,
// interval, solfege) consumes these types.

export type SourceType = 'system' | 'microphone' | 'file';
export type NoteStatus = 'tentative' | 'confirmed' | 'corrected' | 'uncertain';
export type NoteSource = 'auto' | 'manual';
export type Direction = 'up' | 'down' | 'unison';
export type IntervalQuality = 'P' | 'M' | 'm' | 'A' | 'd';
export type ScaleType = 'major' | 'minor';

/** One pitch estimation frame (produced by Python YIN, consumed by TS). */
export interface PitchEstimate {
  /** Seconds since the start of the current stream. */
  timestamp: number;
  /** Fundamental frequency in Hz, or null when unvoiced. */
  frequencyHz: number | null;
  /** m = 69 + 12 * log2(f / 440), or null when unvoiced. */
  continuousMidi: number | null;
  /** Rounded MIDI candidate, or null when unvoiced. */
  roundedMidi: number | null;
  /** 0..1 — not a calibrated probability. */
  confidence: number;
  /** True when the frame contains a plausible voiced pitch. */
  voiced: boolean;
  /** Which pitch algorithm produced this frame. */
  algorithm: string;
  diagnostics: PitchDiagnostics;
}

export interface PitchDiagnostics {
  rms?: number;
  aperiodicity?: number;
  clipped?: boolean;
}

export interface Correction {
  from: number;
  to: number;
  at: string;
}

/** A confirmed (or explicitly corrected) musical note event. */
export interface NoteEvent {
  /** Stable, unique id. Never reused. */
  id: string;
  /** 0-based position in the track. Assigned by the track store. */
  index: number;
  /** Seconds. */
  startTime: number;
  /** Seconds. */
  endTime: number;
  midiNote: number;
  noteName: string;
  frequencyHz: number | null;
  confidence: number;
  status: NoteStatus;
  source: NoteSource;
  /** The auto-detected MIDI before any manual correction. */
  originalMidiNote: number | null;
  correctionHistory: Correction[];
}

export interface IntervalEvent {
  previousNoteId: string;
  currentNoteId: string;
  deltaSemitones: number;
  direction: Direction;
  intervalNumber: number;
  intervalQuality: IntervalQuality;
  intervalName: string;
  octaveDisplacement: number;
}

export interface ProcessingConfig {
  sampleRate: number;
  frameSize: number;
  hopSize: number;
  [key: string]: unknown;
}

export interface MelodyTrack {
  trackId: string;
  createdAt: string;
  sourceType: SourceType;
  selectedKey: string;
  notes: NoteEvent[];
  processingConfig: ProcessingConfig;
  revision: number;
}

export interface KeyMapping {
  keySignature: string;
  scaleType: ScaleType;
  noteMidi: number;
  noteName: string;
  /** 1..7 when in-scale, otherwise null. */
  scaleDegree: number | null;
  solfege: string;
  inScale: boolean;
  alteration: 'sharp' | 'flat' | null;
}
