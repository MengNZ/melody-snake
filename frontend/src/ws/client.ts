// Thin WebSocket client for the Python backend (/ws).

import type { PitchDiagnostics, PitchEstimate } from '../core/types';

export type SourceType = 'system' | 'microphone' | 'file';

export interface BackendStatus {
  state: 'running' | 'paused' | 'ended' | 'error';
  sampleRate: number | null;
  source: string | null;
  error: string | null;
}

export interface ClientCallbacks {
  onPitch: (frame: PitchEstimate) => void;
  onStatus: (status: BackendStatus) => void;
  onOpen: () => void;
  onClose: () => void;
  onError: (message: string) => void;
}

export class BackendClient {
  private ws: WebSocket | null = null;

  constructor(
    private url: string,
    private cb: ClientCallbacks,
  ) {}

  connect(): void {
    this.ws = new WebSocket(this.url);
    this.ws.onopen = () => this.cb.onOpen();
    this.ws.onclose = () => this.cb.onClose();
    this.ws.onerror = () => this.cb.onError('WebSocket connection error');
    this.ws.onmessage = (ev) => {
      let msg: unknown;
      try {
        msg = JSON.parse(String(ev.data));
      } catch {
        return;
      }
      const m = msg as { type?: string } & Record<string, unknown>;
      if (m.type === 'pitch') {
        this.cb.onPitch(this.toPitchEstimate(m));
      } else if (m.type === 'status') {
        this.cb.onStatus(m as unknown as BackendStatus);
      }
    };
  }

  get connected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  private toPitchEstimate(m: Record<string, unknown>): PitchEstimate {
    return {
      timestamp: Number(m.timestamp),
      frequencyHz: m.frequencyHz === null || m.frequencyHz === undefined ? null : Number(m.frequencyHz),
      continuousMidi: m.continuousMidi === null || m.continuousMidi === undefined ? null : Number(m.continuousMidi),
      roundedMidi: m.roundedMidi === null || m.roundedMidi === undefined ? null : Number(m.roundedMidi),
      confidence: Number(m.confidence),
      voiced: Boolean(m.voiced),
      algorithm: String(m.algorithm ?? ''),
      diagnostics: (m.diagnostics ?? {}) as PitchDiagnostics,
    };
  }

  start(source: SourceType, file?: string): void {
    this.send({ type: 'start', source, file });
  }

  pause(): void {
    this.send({ type: 'pause' });
  }

  resume(): void {
    this.send({ type: 'resume' });
  }

  stop(): void {
    this.send({ type: 'stop' });
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  private send(msg: unknown): void {
    if (this.connected) {
      this.ws!.send(JSON.stringify(msg));
    }
  }
}
