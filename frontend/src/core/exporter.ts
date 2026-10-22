// Export the track + intervals as JSON or CSV (for offline review / spreadsheet).

import type { IntervalEvent, MelodyTrack } from './types';
import { mapToSolfege } from './solfege';
import { midiToOctave } from './midi';

export function trackToJSON(track: MelodyTrack, intervals: IntervalEvent[]): string {
  return JSON.stringify({ track, intervals }, null, 2);
}

export function trackToCSV(track: MelodyTrack, intervals: IntervalEvent[]): string {
  const header = [
    'index',
    'noteName',
    'midiNote',
    'octave',
    'solfege',
    'inScale',
    'startTime',
    'endTime',
    'duration',
    'confidence',
    'status',
    'intervalName',
    'deltaSemitones',
    'direction',
  ];

  const rows = track.notes.map((n, i) => {
    const mapping = mapToSolfege(n.midiNote, track.selectedKey, 'major');
    const prev = i > 0 ? intervals[i - 1] : null;
    return [
      String(n.index),
      n.noteName,
      String(n.midiNote),
      String(midiToOctave(n.midiNote)),
      mapping.solfege,
      String(mapping.inScale),
      n.startTime.toFixed(3),
      n.endTime.toFixed(3),
      (n.endTime - n.startTime).toFixed(3),
      n.confidence.toFixed(3),
      n.status,
      prev ? prev.intervalName : '',
      prev ? String(prev.deltaSemitones) : '',
      prev ? prev.direction : '',
    ];
  });

  return [header.join(','), ...rows.map((r) => r.join(','))].join('\n');
}
