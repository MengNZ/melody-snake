// Standalone CLI: pitch frames JSON -> note events JSON.
// Reuses the exact NoteEventDetector that the app uses (single source of truth),
// so the benchmark evaluates the real segmentation, not a re-implementation.
//
// Usage: node dist/segment-cli.mjs <input-frames.json> <output-notes.json>

import { readFileSync, writeFileSync } from 'node:fs';
import { DEFAULT_SEGMENTATION_CONFIG, NoteEventDetector, type SegmentationConfig } from '../src/core/segmentation';
import type { NoteEvent, PitchEstimate } from '../src/core/types';

const [, , inPath, outPath, configPath] = process.argv;
if (!inPath || !outPath) {
  console.error('usage: segment-cli.mjs <input-frames.json> <output-notes.json>');
  process.exit(2);
}

const frames = JSON.parse(readFileSync(inPath, 'utf8')) as PitchEstimate[];
const overrides = configPath ? JSON.parse(readFileSync(configPath, 'utf8')) as Partial<SegmentationConfig> : {};
const detector = new NoteEventDetector({ ...DEFAULT_SEGMENTATION_CONFIG, ...overrides });
const events: NoteEvent[] = [];

for (const frame of frames) {
  for (const out of detector.process(frame)) {
    if (out.type === 'commit') events.push(out.event);
  }
}
for (const out of detector.flush()) {
  if (out.type === 'commit') events.push(out.event);
}

writeFileSync(outPath, JSON.stringify(events, null, 2));
