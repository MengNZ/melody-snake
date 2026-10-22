import { useState } from 'react';
import type { IntervalEvent, NoteEvent } from '../core/types';
import { solfegeLabel } from '../core/solfege';
import { midiToNoteName, noteNameToMidi } from '../core/midi';

interface Props {
  note: NoteEvent | null;
  prevInterval: IntervalEvent | null;
  nextInterval: IntervalEvent | null;
  selectedKey: string;
  onEdit: (id: string, midi: number) => void;
  onUndo: () => void;
}

export function NoteInspector({ note, prevInterval, nextInterval, selectedKey, onEdit, onUndo }: Props) {
  const [editValue, setEditValue] = useState('');
  const [editError, setEditError] = useState('');

  if (!note) {
    return (
      <aside className="inspector">
        <h2>音符详情</h2>
        <p className="muted">点击轨迹中的音符查看详情。</p>
      </aside>
    );
  }

  const applyEdit = () => {
    const midi = noteNameToMidi(editValue);
    if (midi === null) {
      setEditError('无法解析音名，例如 C4 或 F#4');
      return;
    }
    setEditError('');
    onEdit(note.id, midi);
    setEditValue('');
  };

  return (
    <aside className="inspector">
      <h2>音符详情</h2>
      <dl>
        <dt>序号</dt>
        <dd>#{note.index + 1}</dd>
        <dt>音名</dt>
        <dd>{note.noteName}</dd>
        <dt>MIDI</dt>
        <dd>{note.midiNote}</dd>
        <dt>唱名</dt>
        <dd>{solfegeLabel(note.midiNote, selectedKey)}</dd>
        <dt>起止</dt>
        <dd>
          {note.startTime.toFixed(2)}s – {note.endTime.toFixed(2)}s
        </dd>
        <dt>时长</dt>
        <dd>{(note.endTime - note.startTime).toFixed(2)}s</dd>
        <dt>置信度</dt>
        <dd>{note.confidence.toFixed(2)}</dd>
        <dt>状态</dt>
        <dd>{note.status}</dd>
        <dt>与前音</dt>
        <dd>{prevInterval ? `${prevInterval.intervalName}（${prevInterval.direction}）` : '—'}</dd>
        <dt>与后音</dt>
        <dd>{nextInterval ? `${nextInterval.intervalName}（${nextInterval.direction}）` : '—'}</dd>
        {note.originalMidiNote !== null && (
          <>
            <dt>原始音</dt>
            <dd>{midiToNoteName(note.originalMidiNote)}</dd>
          </>
        )}
      </dl>

      <div className="edit-row">
        <input
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          placeholder={`修正为，例如 ${note.noteName}`}
        />
        <button onClick={applyEdit}>修正</button>
        <button onClick={onUndo}>撤销上次修正</button>
      </div>
      {editError && <p className="error">{editError}</p>}
    </aside>
  );
}
