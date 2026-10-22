import type { BackendStatus } from '../ws/client';
import type { CurrentNoteInfo, DetectorStateName } from '../core/segmentation';

interface Props {
  status: BackendStatus;
  connected: boolean;
  state: DetectorStateName;
  noteCount: number;
  current: CurrentNoteInfo | null;
}

export function DiagnosticsPanel({ status, connected, state, noteCount, current }: Props) {
  return (
    <footer className="diagnostics">
      <span>连接：{connected ? '已连接' : '未连接'}</span>
      <span>后端状态：{status.state}</span>
      <span>采样率：{status.sampleRate ?? '—'}</span>
      <span>切分状态：{state}</span>
      <span>已确认音符：{noteCount}</span>
      <span>当前置信度：{current ? current.confidence.toFixed(2) : '—'}</span>
      {status.error && <span className="error">错误：{status.error}</span>}
    </footer>
  );
}
