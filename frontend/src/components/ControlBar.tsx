import { useRef, useState } from 'react';
import type { SourceType } from '../ws/client';
import { SUPPORTED_MAJOR_KEYS } from '../core/solfege';
import { solfegeLabel } from '../core/solfege';
import type { CurrentNoteInfo } from '../core/segmentation';

interface Props {
  source: SourceType;
  onSourceChange: (s: SourceType) => void;
  filePath: string;
  onFilePathChange: (p: string) => void;
  selectedKey: string;
  onKeyChange: (k: string) => void;
  connected: boolean;
  running: boolean;
  analyzing: boolean;
  current: CurrentNoteInfo | null;
  onAnalyze: (duration: number) => void;
  onAnalyzeFile: (file: File) => void;
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  onNew: () => void;
  onExportJson: () => void;
  onExportCsv: () => void;
}

export function ControlBar(props: Props) {
  const [duration, setDuration] = useState(20);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const currentLabel = props.current ? solfegeLabel(props.current.midiNote, props.selectedKey) : '—';
  return (
    <header className="control-bar">
      <div className="brand">
        <h1>Melody Snake</h1>
        <span className={`conn ${props.connected ? 'on' : 'off'}`}>{props.connected ? '已连接' : '未连接'}</span>
      </div>

      <div className="group">
        <label>输入源</label>
        <select value={props.source} onChange={(e) => props.onSourceChange(e.target.value as SourceType)}>
          <option value="system">系统音频</option>
          <option value="microphone">麦克风</option>
          <option value="file">音频文件</option>
        </select>
        {props.source === 'file' && (
          <input
            className="file-path"
            value={props.filePath}
            onChange={(e) => props.onFilePathChange(e.target.value)}
            placeholder="WAV 文件路径，例如 D:\\song.wav"
          />
        )}
      </div>

      <div className="group">
        <label>调性</label>
        <select value={props.selectedKey} onChange={(e) => props.onKeyChange(e.target.value)}>
          {SUPPORTED_MAJOR_KEYS.map((k) => (
            <option key={k} value={k}>
              {k} 大调
            </option>
          ))}
        </select>
      </div>

      <div className="group current">
        <span>当前音</span>
        <strong>{props.current ? props.current.noteName : '—'}</strong>
        <span className="muted">{props.current ? currentLabel : ''}</span>
      </div>

      <div className="group buttons">
        <button className="analyze" onClick={() => props.onAnalyze(duration)} disabled={props.analyzing}>
          {props.analyzing ? '分析中…（约40秒）' : `分析系统音频 ${duration}s`}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".wav,audio/wav"
          hidden
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            if (file) props.onAnalyzeFile(file);
            event.currentTarget.value = '';
          }}
        />
        <button className="analyze" onClick={() => fileInputRef.current?.click()} disabled={props.analyzing}>
          {props.analyzing ? '离线分析中…' : '选择 WAV 离线分析'}
        </button>
        <input
          className="duration"
          type="number"
          min={5}
          max={120}
          value={duration}
          onChange={(e) => setDuration(Number(e.target.value) || 20)}
          title="录制时长（秒）"
        />
        <button onClick={props.onStart} disabled={props.running}>
          开始
        </button>
        <button onClick={props.onPause} disabled={!props.running}>
          暂停
        </button>
        <button onClick={props.onResume} disabled={props.running}>
          继续
        </button>
        <button onClick={props.onStop}>停止</button>
        <button onClick={props.onNew}>新建轨迹</button>
        <button onClick={props.onExportJson}>导出 JSON</button>
        <button onClick={props.onExportCsv}>导出 CSV</button>
      </div>
    </header>
  );
}
