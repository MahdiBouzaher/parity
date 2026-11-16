import type { Explanation } from '../api/types'
import { sv } from '../lib/format'
import { Button } from './Button'

export type WhyState = 'differs' | 'fixed' | 'kept' | 'match'

interface Props {
  state: WhyState
  total: number
  explanation: Explanation
  fixedBody: string
  canFix: boolean
  busy: 'fix' | 'keep' | 'undo' | null
  swap: boolean
  onFix: () => void
  onKeep: () => void
  onUndo: () => void
  index: number
}

export function WhyCard({ state, total, explanation, fixedBody, canFix, busy, swap, onFix, onKeep, onUndo, index }: Props) {
  const cls = 'panel why rise' + (swap ? ' swap' : '')
  const style = sv({ '--i': index })
  const blocked = busy !== null

  if (state === 'match') {
    return (
      <div className={cls} style={style}>
        <div>
          <h3>
            <span className="okmark"></span>Parity reached
          </h3>
          <p>{`All ${total} checks match. Nothing to fix.`}</p>
        </div>
      </div>
    )
  }

  if (state === 'fixed') {
    return (
      <div className={cls} style={style}>
        <div>
          <h3>
            <span className="okmark"></span>Parity reached
          </h3>
          <p>{fixedBody}</p>
        </div>
        <div className="acts">
          <Button onClick={onUndo} disabled={blocked}>
            Undo fix
          </Button>
        </div>
      </div>
    )
  }

  if (state === 'kept') {
    return (
      <div className={cls} style={style}>
        <div>
          <h3>Difference kept</h3>
          <p>It will be listed as an accepted difference in the exported report.</p>
        </div>
        <div className="acts">
          <Button onClick={onUndo} disabled={blocked}>
            Undo
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className={cls} style={style}>
      <div>
        <h3>{explanation.title}</h3>
        {explanation.paragraphs.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
        {explanation.note ? <p className="note">{explanation.note}</p> : null}
        {explanation.source === 'rules' ? (
          <p className="note">Written by the rule layer. Add a key for a model-written explanation.</p>
        ) : null}
      </div>
      <div className="acts">
        <Button onClick={onKeep} disabled={blocked}>
          Keep as is
        </Button>
        {canFix ? (
          <Button variant="primary" onClick={onFix} loading={busy === 'fix'} disabled={blocked}>
            {busy === 'fix' ? 'Re-running' : 'Apply fix and re-run'}
          </Button>
        ) : null}
      </div>
    </div>
  )
}
