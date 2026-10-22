// React hook: wires the BackendClient (pitch frames) into the MelodyEngine
// (segmentation + track + intervals + solfege), exposing a throttled snapshot
// plus user actions. No music-theory logic lives here — it only connects data.

import { useCallback, useEffect, useRef, useState } from 'react';
import { MelodyEngine, type EngineSnapshot } from '../core/pipeline';
import { trackToCSV, trackToJSON } from '../core/exporter';
import { BackendClient, type BackendStatus, type SourceType } from '../ws/client';

export function useEngine() {
  const engineRef = useRef<MelodyEngine | null>(null);
  if (engineRef.current === null) {
    engineRef.current = new MelodyEngine(undefined, 'system');
  }
  const engine = engineRef.current;

  const [snap, setSnap] = useState<EngineSnapshot>(() => engine.snapshot());
  const [status, setStatus] = useState<BackendStatus>({ state: 'ended', sampleRate: null, source: null, error: null });
  const [connected, setConnected] = useState(false);
  const [source, setSource] = useState<SourceType>('system');
  const [filePath, setFilePath] = useState('');

  const clientRef = useRef<BackendClient | null>(null);
  const rafRef = useRef<number | null>(null);

  const scheduleUpdate = useCallback(() => {
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        setSnap(engine.snapshot());
      });
    }
  }, [engine]);

  useEffect(() => {
    const client = new BackendClient('ws://127.0.0.1:8000/ws', {
      onPitch: (frame) => {
        engine.process(frame);
        scheduleUpdate();
      },
      onStatus: (s) => {
        setStatus(s);
        if (s.state === 'ended') {
          engine.flush();
          scheduleUpdate();
        }
      },
      onOpen: () => setConnected(true),
      onClose: () => setConnected(false),
      onError: (e) => setStatus((prev) => ({ ...prev, state: 'error', error: e })),
    });
    clientRef.current = client;
    client.connect();
    return () => {
      client.disconnect();
      clientRef.current = null;
    };
  }, [engine, scheduleUpdate]);

  const start = useCallback(() => {
    engine.store.newTrack(source);
    scheduleUpdate();
    clientRef.current?.start(source, source === 'file' ? filePath : undefined);
  }, [engine, source, filePath, scheduleUpdate]);

  const pause = useCallback(() => clientRef.current?.pause(), []);
  const resume = useCallback(() => clientRef.current?.resume(), []);
  const stop = useCallback(() => {
    clientRef.current?.stop();
    engine.flush();
    scheduleUpdate();
  }, [engine, scheduleUpdate]);

  const newTrack = useCallback(() => {
    engine.store.newTrack(source);
    scheduleUpdate();
  }, [engine, source, scheduleUpdate]);

  const setKey = useCallback(
    (key: string) => {
      engine.store.setSelectedKey(key);
      scheduleUpdate();
    },
    [engine, scheduleUpdate],
  );

  const editNote = useCallback(
    (id: string, midi: number) => {
      engine.store.editNote(id, midi);
      scheduleUpdate();
    },
    [engine, scheduleUpdate],
  );

  const undo = useCallback(() => {
    engine.store.undo();
    scheduleUpdate();
  }, [engine, scheduleUpdate]);

  const exportJSON = useCallback(() => {
    const s = engine.store.getSnapshot();
    return trackToJSON(s.track, s.intervals);
  }, [engine]);

  const exportCSV = useCallback(() => {
    const s = engine.store.getSnapshot();
    return trackToCSV(s.track, s.intervals);
  }, [engine]);

  const download = useCallback(
    (kind: 'json' | 'csv') => {
      const content = kind === 'json' ? exportJSON() : exportCSV();
      const blob = new Blob([content], { type: kind === 'json' ? 'application/json' : 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `melody-snake.${kind}`;
      a.click();
      URL.revokeObjectURL(url);
    },
    [exportJSON, exportCSV],
  );

  return {
    snap,
    status,
    connected,
    source,
    setSource,
    filePath,
    setFilePath,
    selectedKey: snap.track.track.selectedKey,
    start,
    pause,
    resume,
    stop,
    newTrack,
    setKey,
    editNote,
    undo,
    download,
  };
}
