import { useState } from 'react';
import { useEngine } from './state/useEngine';
import { ControlBar } from './components/ControlBar';
import { MelodyTrack } from './components/MelodyTrack';
import { NoteInspector } from './components/NoteInspector';
import { DiagnosticsPanel } from './components/DiagnosticsPanel';
import './styles.css';

export default function App() {
  const engine = useEngine();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { snap } = engine;
  const notes = snap.track.track.notes;
  const intervals = snap.track.intervals;

  const selected = notes.find((n) => n.id === selectedId) ?? null;
  const selIndex = selected ? selected.index : -1;
  const prevInterval = selected && selIndex > 0 ? intervals[selIndex - 1] : null;
  const nextInterval = selected && selIndex < intervals.length ? intervals[selIndex] : null;

  return (
    <div className="app">
      <ControlBar
        source={engine.source}
        onSourceChange={engine.setSource}
        filePath={engine.filePath}
        onFilePathChange={engine.setFilePath}
        selectedKey={engine.selectedKey}
        onKeyChange={engine.setKey}
        connected={engine.connected}
        running={engine.status.state === 'running'}
        analyzing={engine.analyzing}
        current={snap.current}
        onAnalyze={engine.analyze}
        onAnalyzeFile={engine.analyzeFile}
        onStart={engine.start}
        onPause={engine.pause}
        onResume={engine.resume}
        onStop={engine.stop}
        onNew={engine.newTrack}
        onExportJson={() => engine.download('json')}
        onExportCsv={() => engine.download('csv')}
      />

      <main className="main">
        <MelodyTrack
          notes={notes}
          intervals={intervals}
          selectedKey={engine.selectedKey}
          current={snap.current}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        <NoteInspector
          note={selected}
          prevInterval={prevInterval}
          nextInterval={nextInterval}
          selectedKey={engine.selectedKey}
          onEdit={engine.editNote}
          onUndo={engine.undo}
        />
      </main>

      <DiagnosticsPanel
        status={engine.status}
        connected={engine.connected}
        state={snap.state}
        noteCount={notes.length}
        current={snap.current}
      />
    </div>
  );
}
