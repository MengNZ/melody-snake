import type { IntervalEvent } from '../core/types';

export function IntervalConnector({ interval }: { interval: IntervalEvent }) {
  const arrow = interval.direction === 'up' ? '↑' : interval.direction === 'down' ? '↓' : '→';
  return (
    <div className="connector" title={`${interval.intervalName} ${interval.deltaSemitones} 半音`}>
      <span className="arrow">{arrow}</span>
      <span className="interval">{interval.intervalName}</span>
      <span className="delta">
        {interval.deltaSemitones > 0 ? '+' : ''}
        {interval.deltaSemitones}
      </span>
    </div>
  );
}
