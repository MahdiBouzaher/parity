import { useRef, useState } from 'react'
import { errorMessage, type HistoryItem } from '../api'
import { Button } from '../components/Button'
import { Chip } from '../components/Chip'
import { sv } from '../lib/format'
import { nav } from '../state/router'
import { useStore } from '../state/store'
import { useHistory } from '../state/useHistory'

const when = (iso: string) =>
  new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })

function Result({ item }: { item: HistoryItem }) {
  if (item.status === 'failed') return <span className="hfail">Failed</span>
  if (item.status !== 'done') return <span className="hfail">{item.status === 'running' ? 'Running' : 'Cancelled'}</span>
  if (item.state === 'fixed') return <Chip variant="ok" text="Fixed" />
  if (item.state === 'match') return <Chip variant="ok" text="Match" />
  if (item.state === 'kept') return <Chip variant="kept" text="Kept" />
  return <Chip variant="warn" text="Differs" />
}

export function HistoryScreen() {
  const { items, error, remove } = useHistory()
  const { toast } = useStore()
  const [armed, setArmed] = useState<string | null>(null)
  const timer = useRef(0)

  const del = async (id: string) => {
    if (armed !== id) {
      setArmed(id)
      clearTimeout(timer.current)
      timer.current = window.setTimeout(() => setArmed(null), 3000)
      return
    }
    clearTimeout(timer.current)
    setArmed(null)
    try {
      await remove(id)
    } catch (e) {
      toast(errorMessage(e))
    }
  }

  return (
    <>
      <h2 className="run-title rise" style={sv({ '--i': 0 })}>
        History
      </h2>
      <p className="run-sub rise" style={sv({ '--i': 1 })}>
        Every run is saved on this machine.
      </p>
      {error ? <p className="hempty rise">{error}</p> : null}
      {items && items.length === 0 ? (
        <div className="hempty rise" style={sv({ '--i': 2 })}>
          <p>No runs yet. Translate a program to see it here.</p>
          <Button onClick={() => nav('/')}>Translate</Button>
        </div>
      ) : null}
      {items && items.length > 0 ? (
        <div className="panel tbl rise" style={sv({ '--i': 2 })}>
          <div className="tscroll">
            <div className="hin" role="table" aria-label="Runs">
              <div className="hrow head" role="row">
                <div className="hlink">
                  <span>Program</span>
                  <span>Date</span>
                  <span>Result</span>
                  <span className="hn">Checks</span>
                </div>
                <span></span>
              </div>
              {items.map((it, k) => (
                <div className="hrow in" role="row" key={it.id} style={sv({ '--k': k })}>
                  <button className="hlink" onClick={() => nav('/report/' + it.id)}>
                    <span className="hname">{it.filename}</span>
                    <span className="hdate">{when(it.created_at)}</span>
                    <span>
                      <Result item={it} />
                    </span>
                    <span className="hn">{`${it.matched} / ${it.total}`}</span>
                  </button>
                  <button className="hdel" onClick={() => void del(it.id)}>
                    {armed === it.id ? 'Confirm' : 'Delete'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
