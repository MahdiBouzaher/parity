import type { ReactNode } from 'react'
import { sv } from '../lib/format'
import { CountText } from './CountText'

export type SegState = 'ok' | 'warn' | 'kept'

export function Segments({ states }: { states: SegState[] }) {
  return (
    <div className="segs" aria-hidden="true">
      {states.map((s, i) => (
        <span key={i} className={'seg' + (s === 'warn' ? ' warn' : s === 'kept' ? ' kept' : '')} style={sv({ '--k': i })}></span>
      ))}
    </div>
  )
}

export function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="stat">
      <small>{label}</small>
      <b>{children}</b>
    </div>
  )
}

interface Props {
  matched: number
  total: number
  segments: SegState[]
  rows: number
  seconds: number
  tolerance: string
  index: number
}

export function Summary({ matched, total, segments, rows, seconds, tolerance, index }: Props) {
  return (
    <div className="panel summary rise" style={sv({ '--i': index })}>
      <div className="sum-l">
        <div className="big">
          <CountText to={matched} dur={700} firstDur={900} delay={450} /> <span className="dim">/ {total}</span>
        </div>
        <p>checks match</p>
        <Segments states={segments} />
      </div>
      <div className="sum-r">
        <Stat label="Compared">
          <CountText to={rows} suffix=" rows" dur={700} firstDur={1100} delay={450} />
        </Stat>
        <Stat label="Run time">
          <CountText to={seconds} decimals={1} suffix=" s" dur={700} firstDur={1100} delay={450} />
        </Stat>
        <Stat label="Tolerance">{tolerance}</Stat>
      </div>
    </div>
  )
}
