// MelodyEngine — wires the NoteEventDetector to the MelodyTrackStore.
// The React UI consumes this; tests drive it with synthetic pitch frames.

import type { PitchEstimate, SourceType } from './types';
import {
  NoteEventDetector,
  type CurrentNoteInfo,
  type DetectorOutput,
  type DetectorStateName,
  type SegmentationConfig,
} from './segmentation';
import { MelodyTrackStore, type TrackSnapshot } from './trackStore';

export interface EngineSnapshot {
  track: TrackSnapshot;
  current: CurrentNoteInfo | null;
  state: DetectorStateName;
}

export class MelodyEngine {
  readonly detector: NoteEventDetector;
  readonly store: MelodyTrackStore;
  private current: CurrentNoteInfo | null = null;
  private state: DetectorStateName = 'IDLE';

  constructor(config?: SegmentationConfig, sourceType: SourceType = 'file') {
    this.detector = new NoteEventDetector(config);
    this.store = new MelodyTrackStore(sourceType);
  }

  /** Feed one pitch frame; committed notes are appended to the store. */
  process(frame: PitchEstimate): void {
    for (const out of this.detector.process(frame)) {
      this.applyOutput(out);
    }
  }

  /** Feed a batch of frames in order. */
  processAll(frames: PitchEstimate[]): void {
    for (const frame of frames) this.process(frame);
  }

  /** Flush any in-flight note at end of stream. */
  flush(): void {
    for (const out of this.detector.flush()) this.applyOutput(out);
  }

  private applyOutput(out: DetectorOutput): void {
    if (out.type === 'commit') {
      this.store.appendNote({
        startTime: out.event.startTime,
        endTime: out.event.endTime,
        midiNote: out.event.midiNote,
        confidence: out.event.confidence,
      });
    } else if (out.type === 'current') {
      this.current = out.note;
    } else if (out.type === 'state') {
      this.state = out.state;
    }
  }

  snapshot(): EngineSnapshot {
    return { track: this.store.getSnapshot(), current: this.current, state: this.state };
  }
}
