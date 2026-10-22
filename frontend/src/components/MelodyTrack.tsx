import { Fragment } from 'react';
import type { IntervalEvent, NoteEvent } from '../core/types';
import type { CurrentNoteInfo } from '../core/segmentation';
import { solfegeLabel } from '../core/solfege';
import { MelodyNode } from './MelodyNode';
import { IntervalConnector } from './IntervalConnector';

interface Props {
  notes: NoteEvent[];
  intervals: IntervalEvent[];
  selectedKey: string;
  current: CurrentNoteInfo | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function MelodyTrack({ notes, intervals, selectedKey, current, selectedId, onSelect }: Props) {
  return (
    <section className="melody-track">
      <div className="track-scroll">
        <div className="track-row">
          {notes.map((n, i) => (
            <Fragment key={n.id}>
              {i > 0 && <IntervalConnector interval={intervals[i - 1]} />}
              <MelodyNode
                note={n}
                solfege={solfegeLabel(n.midiNote, selectedKey)}
                selected={n.id === selectedId}
                onClick={() => onSelect(n.id)}
              />
            </Fragment>
          ))}

          {current && (
            <Fragment>
              {notes.length > 0 && <span className="connector pending">…</span>}
              <div className="node current">
                <span className="index">?</span>
                <span className="solfege">{solfegeLabel(current.midiNote, selectedKey)}</span>
                <span className="name">{current.noteName}</span>
                <span className="time">{(current.durationMs / 1000).toFixed(1)}s</span>
              </div>
            </Fragment>
          )}

          {notes.length === 0 && !current && (
            <p className="empty">开始后，已确认的音符会按时间顺序出现在这里，历史不会被覆盖。</p>
          )}
        </div>
      </div>
    </section>
  );
}
