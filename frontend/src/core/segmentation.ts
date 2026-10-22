// NoteEventDetector — turns a stream of PitchEstimate frames into note events
// via an explicit, testable state machine. This is the heart of "do NOT turn
// every pitch frame into a note".

import type { NoteEvent, PitchEstimate } from './types';
import { midiToNoteName } from './midi';

export type DetectorStateName = 'IDLE' | 'CANDIDATE' | 'ACTIVE' | 'TRANSITION';

export interface SegmentationConfig {
  /** Max pitch deviation (semitones) tolerated inside a single note. */
  pitchToleranceSemitones: number;
  /** Notes shorter than this are dropped as noise. */
  minNoteDurationMs: number;
  /** Unvoiced gap (ms) that ends the current note. */
  minGapMs: number;
  /** Consecutive frames at a new pitch needed to confirm a note change. */
  candidateConfirmFrames: number;
  /** Max pitch spread (semitones) over the confirm window; beyond it the pitch
   *  is still gliding, so the change is NOT yet confirmed. */
  transitionStabilitySemitones: number;
  /** Frames with confidence below this are treated as unvoiced. */
  minConfidence: number;
  /** Max rolling-window size for the robust pitch median. */
  maxMidiBuffer: number;
}

export const DEFAULT_SEGMENTATION_CONFIG: SegmentationConfig = {
  pitchToleranceSemitones: 0.7,
  minNoteDurationMs: 30,
  minGapMs: 45,
  candidateConfirmFrames: 3,
  transitionStabilitySemitones: 0.3,
  minConfidence: 0.25,
  maxMidiBuffer: 12,
};

export interface CurrentNoteInfo {
  startTime: number;
  midiNote: number;
  noteName: string;
  confidence: number;
  durationMs: number;
}

export type DetectorOutput =
  | { type: 'state'; state: DetectorStateName }
  | { type: 'current'; note: CurrentNoteInfo | null }
  | { type: 'commit'; event: NoteEvent };

export class NoteEventDetector {
  private state: DetectorStateName = 'IDLE';
  private noteStartTime = 0;
  private midiBuffer: number[] = [];
  private confidenceBuffer: number[] = [];
  private lastVoicedTime = 0;

  private transitionStartTime = 0;
  private transitionMidi: number | null = null;
  private transitionCount = 0;
  private transitionBuffer: number[] = [];
  private transitionConfidences: number[] = [];

  private eventCounter = 0;

  constructor(private cfg: SegmentationConfig = DEFAULT_SEGMENTATION_CONFIG) {}

  get currentState(): DetectorStateName {
    return this.state;
  }

  private isVoiced(frame: PitchEstimate): boolean {
    return frame.voiced && frame.roundedMidi != null && frame.confidence >= this.cfg.minConfidence;
  }

  private median(values: number[]): number {
    if (values.length === 0) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  }

  private currentNoteMidi(): number {
    return this.median(this.midiBuffer);
  }

  private currentConfidence(): number {
    if (this.confidenceBuffer.length === 0) return 0;
    return this.confidenceBuffer.reduce((a, b) => a + b, 0) / this.confidenceBuffer.length;
  }

  private pushVoiced(frame: PitchEstimate, midi: number): void {
    this.midiBuffer.push(midi);
    this.confidenceBuffer.push(frame.confidence);
    if (this.midiBuffer.length > this.cfg.maxMidiBuffer) this.midiBuffer.shift();
    if (this.confidenceBuffer.length > this.cfg.maxMidiBuffer) this.confidenceBuffer.shift();
    this.lastVoicedTime = frame.timestamp;
  }

  private resetNote(): void {
    this.midiBuffer = [];
    this.confidenceBuffer = [];
    this.transitionMidi = null;
    this.transitionCount = 0;
    this.transitionBuffer = [];
    this.transitionConfidences = [];
  }

  private commitNote(): NoteEvent | null {
    if (this.midiBuffer.length === 0) return null;
    const durationMs = (this.lastVoicedTime - this.noteStartTime) * 1000;
    if (durationMs < this.cfg.minNoteDurationMs) {
      this.resetNote();
      return null;
    }
    const midi = Math.round(this.currentNoteMidi());
    this.eventCounter += 1;
    const event: NoteEvent = {
      id: `detector-${this.eventCounter}`,
      index: -1, // assigned by the track store on append
      startTime: this.noteStartTime,
      endTime: this.lastVoicedTime,
      midiNote: midi,
      noteName: midiToNoteName(midi),
      frequencyHz: null,
      confidence: this.currentConfidence(),
      status: 'confirmed',
      source: 'auto',
      originalMidiNote: null,
      correctionHistory: [],
    };
    this.resetNote();
    return event;
  }

  private currentInfo(now: number): CurrentNoteInfo {
    const midi = Math.round(this.currentNoteMidi());
    return {
      startTime: this.noteStartTime,
      midiNote: midi,
      noteName: midiToNoteName(midi),
      confidence: this.currentConfidence(),
      durationMs: (now - this.noteStartTime) * 1000,
    };
  }

  private startTransition(midi: number, timestamp: number, confidence: number): void {
    this.transitionStartTime = timestamp;
    this.transitionMidi = midi;
    this.transitionCount = 1;
    this.transitionBuffer = [midi];
    this.transitionConfidences = [confidence];
  }

  /** Feed one frame; returns zero or more outputs to apply downstream. */
  process(frame: PitchEstimate): DetectorOutput[] {
    const outputs: DetectorOutput[] = [];
    const voiced = this.isVoiced(frame);

    if (!voiced) {
      if (this.state !== 'IDLE') {
        const gapMs = (frame.timestamp - this.lastVoicedTime) * 1000;
        if (gapMs >= this.cfg.minGapMs) {
          const committed = this.commitNote();
          if (committed) outputs.push({ type: 'commit', event: committed });
          this.state = 'IDLE';
          outputs.push({ type: 'state', state: this.state });
          outputs.push({ type: 'current', note: null });
        }
        // else: short gap — keep the note alive.
      }
      return outputs;
    }

    const midi = frame.continuousMidi as number;
    const now = frame.timestamp;

    if (this.state === 'IDLE') {
      this.noteStartTime = now;
      this.pushVoiced(frame, midi);
      this.state = 'CANDIDATE';
      outputs.push({ type: 'state', state: this.state });
      outputs.push({ type: 'current', note: this.currentInfo(now) });
      return outputs;
    }

    if (this.state === 'CANDIDATE') {
      const noteMidi = this.currentNoteMidi();
      if (Math.abs(midi - noteMidi) <= this.cfg.pitchToleranceSemitones) {
        this.pushVoiced(frame, midi);
        if (this.midiBuffer.length >= this.cfg.candidateConfirmFrames) {
          this.state = 'ACTIVE';
          outputs.push({ type: 'state', state: this.state });
        }
        outputs.push({ type: 'current', note: this.currentInfo(now) });
      } else {
        // Candidate pitch moved: restart the candidate at the new pitch.
        this.noteStartTime = now;
        this.resetNote();
        this.pushVoiced(frame, midi);
        outputs.push({ type: 'current', note: this.currentInfo(now) });
      }
      return outputs;
    }

    if (this.state === 'ACTIVE') {
      const noteMidi = this.currentNoteMidi();
      if (Math.abs(midi - noteMidi) <= this.cfg.pitchToleranceSemitones) {
        this.pushVoiced(frame, midi);
        this.transitionMidi = null;
        this.transitionCount = 0;
        outputs.push({ type: 'current', note: this.currentInfo(now) });
        return outputs;
      }
      this.startTransition(midi, now, frame.confidence);
      this.state = 'TRANSITION';
      outputs.push({ type: 'state', state: this.state });
      return outputs;
    }

    if (this.state === 'TRANSITION') {
      const noteMidi = this.currentNoteMidi();
      if (Math.abs(midi - noteMidi) <= this.cfg.pitchToleranceSemitones) {
        // Vibrato/glide returned to the original note: abort the transition.
        this.pushVoiced(frame, midi);
        this.transitionMidi = null;
        this.transitionCount = 0;
        this.state = 'ACTIVE';
        outputs.push({ type: 'state', state: this.state });
        outputs.push({ type: 'current', note: this.currentInfo(now) });
        return outputs;
      }

      if (this.transitionMidi !== null && Math.abs(midi - this.transitionMidi) <= this.cfg.pitchToleranceSemitones) {
        this.transitionCount += 1;
        this.transitionBuffer.push(midi);
        this.transitionConfidences.push(frame.confidence);
        if (this.transitionCount >= this.cfg.candidateConfirmFrames) {
          const recent = this.transitionBuffer.slice(-this.cfg.candidateConfirmFrames);
          const spread = Math.max(...recent) - Math.min(...recent);
          if (spread > this.cfg.transitionStabilitySemitones) {
            return outputs; // pitch is still gliding, not a settled note
          }
          // Confirmed pitch change. Capture the new note's data BEFORE
          // commitNote() resets the transition buffers, then commit the old
          // note and start the new one.
          const newStartTime = this.transitionStartTime;
          const newMidiBuffer = [...this.transitionBuffer];
          const newConfidenceBuffer = [...this.transitionConfidences];

          const committed = this.commitNote();
          if (committed) outputs.push({ type: 'commit', event: committed });

          this.noteStartTime = newStartTime;
          this.midiBuffer = newMidiBuffer;
          this.confidenceBuffer = newConfidenceBuffer;
          this.lastVoicedTime = now;
          this.transitionMidi = null;
          this.transitionCount = 0;
          this.transitionBuffer = [];
          this.transitionConfidences = [];
          this.state = 'ACTIVE';
          outputs.push({ type: 'state', state: this.state });
          outputs.push({ type: 'current', note: this.currentInfo(now) });
        }
        return outputs;
      }

      // Transition target moved again: retarget to this new pitch.
      this.startTransition(midi, now, frame.confidence);
      return outputs;
    }

    return outputs;
  }

  /** End of stream: commit any note still in flight. */
  flush(): DetectorOutput[] {
    const outputs: DetectorOutput[] = [];
    const committed = this.commitNote();
    if (committed) outputs.push({ type: 'commit', event: committed });
    this.state = 'IDLE';
    this.resetNote();
    outputs.push({ type: 'state', state: this.state });
    outputs.push({ type: 'current', note: null });
    return outputs;
  }
}
