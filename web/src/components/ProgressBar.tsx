import { sv } from '../lib/format'

export function ProgressBar({ percent, index }: { percent: number; index: number }) {
  return (
    <div
      className="bar rise"
      style={sv({ '--i': index })}
      role="progressbar"
      aria-label="Translation progress"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(percent)}
    >
      <i style={{ width: percent + '%' }}></i>
    </div>
  )
}
