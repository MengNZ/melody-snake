import type { NoteEvent } from '../core/types';

interface Props {
  note: NoteEvent;
  solfege: string;
  selected: boolean;
  onClick: () => void;
}

export function MelodyNode({ note, solfege, selected, onClick }: Props) {
  return (
    <div className={`node ${selected ? 'selected' : ''} ${note.status === 'corrected' ? 'corrected' : ''}`} onClick={onClick}>
      <span className="index">{String(note.index + 1).padStart(2, '0')}</span>
      <span className="solfege">{solfege}</span>
      <span className="name">{note.noteName}</span>
      <span className="time">{note.startTime.toFixed(1)}s</span>
    </div>
  );
}
