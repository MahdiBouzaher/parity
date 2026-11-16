import { useEffect, useRef, useState } from 'react'
import { api, errorMessage } from '../api'
import type { Dataset } from '../api/types'
import { Button } from '../components/Button'
import { DataPreview } from '../components/DataPreview'
import { DropZone } from '../components/DropZone'
import { Tabs } from '../components/Tabs'
import { sv } from '../lib/format'
import { nav } from '../state/router'
import { fileNameOf, useStore } from '../state/store'

type Busy = null | 'input' | 'expected' | 'sample' | 'run'

export function DataScreen() {
  const { state, dispatch, toast } = useStore()
  const { dataset, lang, source } = state
  const [busy, setBusy] = useState<Busy>(null)
  const [table, setTable] = useState('')
  const [tol, setTol] = useState<Record<string, string>>({})
  const tolSaved = useRef<string>('{}')

  useEffect(() => {
    const stop = (e: DragEvent) => e.preventDefault()
    window.addEventListener('dragover', stop)
    window.addEventListener('drop', stop)
    return () => {
      window.removeEventListener('dragover', stop)
      window.removeEventListener('drop', stop)
    }
  }, [])

  useEffect(() => {
    const t: Record<string, string> = {}
    Object.entries(dataset?.tolerances ?? {}).forEach(([k, v]) => {
      t[k] = String(v)
    })
    setTol(t)
    tolSaved.current = JSON.stringify(dataset?.tolerances ?? {})
  }, [dataset?.id, JSON.stringify(dataset?.tolerances ?? {})])

  const expected = dataset?.expected ?? []
  const active = expected.find((e) => e.table === table) ?? expected[0]

  const ensure = async (): Promise<Dataset> => {
    if (dataset) return dataset
    const d = await api.createDataset()
    dispatch({ type: 'dataset', dataset: d })
    return d
  }

  const upload = async (kind: 'input' | 'expected', file: File) => {
    if (!/\.csv$/i.test(file.name) && file.type !== 'text/csv') {
      toast('Choose a CSV file.')
      return
    }
    setBusy(kind)
    try {
      const ds = await ensure()
      const next = kind === 'input' ? await api.uploadInput(ds.id, file) : await api.uploadExpected(ds.id, file)
      dispatch({ type: 'dataset', dataset: next })
      if (kind === 'expected') setTable(next.expected[next.expected.length - 1]?.table ?? '')
    } catch (e) {
      toast(errorMessage(e))
    }
    setBusy(null)
  }

  const remove = async (t: string) => {
    if (!dataset) return
    try {
      dispatch({ type: 'dataset', dataset: await api.deleteExpected(dataset.id, t) })
    } catch (e) {
      toast(errorMessage(e))
    }
  }

  const useSample = async () => {
    setBusy('sample')
    try {
      const ds = await api.sampleDataset(lang)
      dispatch({ type: 'dataset', dataset: ds })
      setTable('')
    } catch (e) {
      toast(errorMessage(e))
    }
    setBusy(null)
  }

  const commitTol = async (): Promise<Dataset | null> => {
    if (!dataset) return null
    const out: Record<string, number> = {}
    for (const [k, v] of Object.entries(tol)) {
      if (v.trim() === '') continue
      const n = Number(v)
      if (!Number.isFinite(n) || n < 0) {
        toast('Tolerance must be a number of zero or more.')
        return null
      }
      if (n > 0) out[k] = n
    }
    if (JSON.stringify(out) === tolSaved.current) return dataset
    try {
      const next = await api.setTolerances(dataset.id, out)
      tolSaved.current = JSON.stringify(next.tolerances)
      dispatch({ type: 'dataset', dataset: next })
      return next
    } catch (e) {
      toast(errorMessage(e))
      return null
    }
  }

  const run = async () => {
    if (!dataset || !dataset.ready || busy) return
    setBusy('run')
    const ds = await commitTol()
    if (!ds) {
      setBusy(null)
      return
    }
    try {
      const { run_id } = await api.createRun({ lang, filename: fileNameOf(state), source, dataset_id: ds.id })
      nav('/running/' + run_id)
    } catch (e) {
      toast(errorMessage(e))
      setBusy(null)
    }
  }

  const tolRows = expected.flatMap((e) =>
    e.columns
      .filter((c) => c.dtype !== 'text')
      .map((c) => ({ key: `${e.table}.${c.name}`.toLowerCase(), label: expected.length > 1 ? `${e.table}.${c.name}` : c.name }))
  )

  return (
    <>
      <h2 className="run-title rise" style={sv({ '--i': 0 })}>
        Add your data
      </h2>
      <p className="run-sub rise" style={sv({ '--i': 1 })}>
        Upload the input sample and the outputs your original program produced. Parity compares the Python against those saved outputs.
      </p>
      <div className="compare rise" style={sv({ '--i': 2 })}>
        <div className="panel dpanel">
          <div className="phead">
            <span>{dataset?.input?.name ?? 'No file yet'}</span>
            <small>Input sample</small>
          </div>
          <DropZone label="Drop a CSV or choose a file" hint="The data your program reads" busy={busy === 'input'} onFile={(f) => upload('input', f)} />
          {dataset?.input ? <DataPreview file={dataset.input} /> : null}
        </div>
        <div className="panel dpanel">
          <div className="phead">
            {expected.length > 1 ? (
              <Tabs
                label="Expected outputs"
                value={active?.table ?? ''}
                onChange={setTable}
                items={expected.map((e) => ({ id: e.table, label: e.table }))}
              />
            ) : (
              <span>{active?.name ?? 'No file yet'}</span>
            )}
            <small>Expected outputs</small>
          </div>
          <DropZone label="Drop a CSV or choose a file" hint="A table your original program produced" busy={busy === 'expected'} onFile={(f) => upload('expected', f)} />
          {active ? (
            <>
              <DataPreview file={active} />
              <div className="dact">
                <button className="link" onClick={() => remove(active.table)}>
                  Remove {active.name}
                </button>
              </div>
            </>
          ) : null}
        </div>
      </div>
      {tolRows.length > 0 ? (
        <div className="panel tolp rise" style={sv({ '--i': 3 })}>
          <div className="phead">
            <span>Tolerances</span>
            <small>Empty means exact</small>
          </div>
          {tolRows.map((r) => (
            <div className="tolrow" key={r.key}>
              <span>{r.label}</span>
              <input
                className="tolin"
                inputMode="decimal"
                placeholder="exact"
                aria-label={`Tolerance for ${r.label}`}
                value={tol[r.key] ?? ''}
                onChange={(e) => setTol({ ...tol, [r.key]: e.target.value })}
                onBlur={() => void commitTol()}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void commitTol()
                }}
              />
            </div>
          ))}
        </div>
      ) : null}
      <div className="dfoot rise" style={sv({ '--i': 4 })}>
        <Button onClick={useSample} loading={busy === 'sample'} disabled={busy !== null}>
          Use sample data
        </Button>
        <Button variant="primary" onClick={run} loading={busy === 'run'} disabled={!dataset?.ready || busy !== null}>
          Run
        </Button>
      </div>
    </>
  )
}
