import { useEffect, useRef, useState } from 'react'
import type { Check } from '../api/types'
import { sv } from '../lib/format'

interface RowProps {
  c: Check
  k: number
  cascade: boolean
  animate: boolean
  focusable: boolean
}

function Row({ c, k, cascade, animate, focusable }: RowProps) {
  const [open, setOpen] = useState(false)
  const prev = useRef(c.actual)
  const flip = animate && prev.current !== c.actual
  useEffect(() => {
    prev.current = c.actual
  }, [c.actual])
  const differs = c.status === 'differs'
  const cls = 'trow click' + (cascade ? ' in' : '') + (differs ? ' diff' : '')
  const toggle = () => setOpen((o) => !o)
  return (
    <>
      <div
        className={cls}
        role="row"
        style={sv({ '--k': k })}
        tabIndex={focusable ? 0 : -1}
        aria-expanded={open}
        onClick={toggle}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            toggle()
          }
        }}
      >
        <span role="cell">{c.label}</span>
        <span className="m" role="cell">
          {c.expected}
        </span>
        <span className="m py" role="cell">
          <b key={c.actual} className={flip ? 'flip' : undefined}>
            {c.actual}
          </b>
        </span>
        <span className="res" role="cell">
          <i></i>
          <em style={{ fontStyle: 'normal' }}>{differs ? 'Differs' : 'Match'}</em>
        </span>
        <span className="delta">{differs && c.delta ? c.delta : ''}</span>
      </div>
      <div className={'rdet' + (open ? ' open' : '')} role="presentation">
        <div>
          <div className="rdin">
            <div className="kv">
              <small>Tolerance</small>
              <span>{c.tolerance}</span>
            </div>
            {c.details ? <p>{c.details}</p> : null}
            {c.mismatches.length > 0 ? (
              <div className="mm">
                {c.mismatches.slice(0, 20).map((m, i) => (
                  <div key={i}>
                    <span>row {m.row}</span>
                    <span>{m.column}</span>
                    <span>{m.expected}</span>
                    <span className="a">{m.actual}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </>
  )
}

interface Props {
  checks: Check[]
  runId: string
  sourceLabel: string
  animate: boolean
  index: number
}

export function ChecksTable({ checks, runId, sourceLabel, animate, index }: Props) {
  const [showAll, setShowAll] = useState(false)
  const pinned = useRef<{ id: string; set: Set<string> }>({ id: runId, set: new Set() })
  if (pinned.current.id !== runId) pinned.current = { id: runId, set: new Set() }
  checks.forEach((c) => {
    if (c.status === 'differs') pinned.current.set.add(c.id)
  })

  const visible: Check[] = []
  const more: Check[] = []
  let seen = 0
  checks.forEach((c) => {
    if (pinned.current.set.has(c.id)) {
      visible.push(c)
      return
    }
    if (seen < 3) {
      seen += 1
      visible.push(c)
      return
    }
    more.push(c)
  })

  return (
    <div className="panel tbl rise" style={sv({ '--i': index })}>
      <div className="tscroll">
        <div className="tin" role="table" aria-label="Checks">
          <div className="trow head" role="row">
            <span role="columnheader">Check</span>
            <span role="columnheader">{sourceLabel}</span>
            <span role="columnheader">Python</span>
            <span role="columnheader">Result</span>
            <span></span>
          </div>
          <div>
            {visible.map((c, i) => (
              <Row key={c.id} c={c} k={i} cascade animate={animate} focusable />
            ))}
          </div>
          <div className={'more' + (showAll ? ' open' : '')}>
            <div>
              <div>
                {more.map((c, i) => (
                  <Row key={c.id} c={c} k={i} cascade={false} animate={animate} focusable={showAll} />
                ))}
              </div>
            </div>
          </div>
          <div className="tfoot">
            <span>
              {more.length === 0
                ? `All ${checks.length} checks match`
                : showAll
                  ? `All ${checks.length} checks`
                  : `${more.length} more ${more.length === 1 ? 'check matches' : 'checks match'}`}
            </span>
            {more.length > 0 ? (
              <button aria-expanded={showAll} onClick={() => setShowAll((v) => !v)}>
                {showAll ? 'Show fewer' : 'Show all'}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}
