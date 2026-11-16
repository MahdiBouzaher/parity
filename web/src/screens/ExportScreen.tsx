import { useEffect, useState } from 'react'
import { useRun } from '../state/useRun'
import { api, errorMessage, type ExportReport } from '../api'
import { Button } from '../components/Button'
import { CodePanel } from '../components/CodePanel'
import { ErrorPanel } from '../components/ErrorPanel'
import { Summary, type SegState } from '../components/Summary'
import { baseName, sv } from '../lib/format'
import { nav } from '../state/router'
import { useStore } from '../state/store'

function HashRow({ label, value, onCopy }: { label: string; value: string; onCopy: (v: string) => void }) {
  return (
    <div className="hx">
      <small>{label}</small>
      <span>{value}</span>
      <button className="link" onClick={() => onCopy(value)}>
        Copy
      </button>
    </div>
  )
}

export function ExportScreen({ id }: { id: string }) {
  const { toast } = useStore()
  const [rep, setRep] = useState<ExportReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { run } = useRun(id)

  useEffect(() => {
    let live = true
    api
      .exportReport(id)
      .then((r) => {
        if (live) setRep(r)
      })
      .catch((e) => {
        if (live) setError(errorMessage(e))
      })
    return () => {
      live = false
    }
  }, [id])

  const copy = (v: string) => {
    const done = () => toast('Copied')
    if (navigator.clipboard) navigator.clipboard.writeText(v).then(done, () => toast('Copy failed'))
    else toast('Copy failed')
  }

  if (error) {
    return (
      <div style={{ marginTop: 56 }}>
        <ErrorPanel title="This report is not available" message={error} onBack={() => nav('/')} index={0} />
      </div>
    )
  }
  if (!rep || !run) return null

  const name = baseName(rep.program.filename)
  const kept = rep.result.state === 'kept'
  const segs: SegState[] = rep.checks.map((c) => (c.status === 'differs' ? (kept ? 'kept' : 'warn') : 'ok'))
  const label = rep.program.lang === 'sas' ? 'SAS' : 'VBA'

  return (
    <>
      <p className="crumb rise" style={sv({ '--i': 0 })}>
        Reports&nbsp; /&nbsp; {name}&nbsp; /&nbsp; Export
      </p>
      <div className="rhead rise" style={sv({ '--i': 1 })}>
        <div className="rtitle">
          <h2>Export report</h2>
        </div>
        <div className="ractions">
          <a className="btn" href={api.exportUrl(id, 'json')} download={name + '-report.json'}>
            Download JSON
          </a>
          <Button onClick={() => window.print()}>Print</Button>
          <a className="btn primary" href={api.exportUrl(id, 'html')} download={name + '-report.html'}>
            Download HTML
          </a>
        </div>
      </div>
      <Summary
        index={2}
        matched={rep.result.matched}
        total={rep.result.total}
        segments={segs}
        rows={run.current.summary.rows_compared}
        seconds={run.current.summary.run_seconds}
        tolerance={run.current.summary.tolerance}
      />
      <div className="panel xpanel rise" style={sv({ '--i': 3 })}>
        <div className="phead">
          <span>Hashes</span>
          <small>SHA-256</small>
        </div>
        <HashRow label="Original code" value={rep.hashes.original_code} onCopy={copy} />
        <HashRow label="Python" value={rep.hashes.python} onCopy={copy} />
        <HashRow label={`Input ${rep.hashes.input.name}`} value={rep.hashes.input.sha256} onCopy={copy} />
        {rep.hashes.expected.map((e) => (
          <HashRow key={e.table} label={`Expected ${e.name}`} value={e.sha256} onCopy={copy} />
        ))}
        <HashRow label="Report" value={rep.report_sha256} onCopy={copy} />
      </div>
      <div className="panel tbl xchecks rise" style={sv({ '--i': 4 })}>
        <div className="tscroll">
          <div className="tin" role="table" aria-label="Checks">
            <div className="trow head" role="row">
              <span role="columnheader">Check</span>
              <span role="columnheader">{label}</span>
              <span role="columnheader">Python</span>
              <span role="columnheader">Result</span>
              <span></span>
            </div>
            {rep.checks.map((c) => (
              <div className={'trow' + (c.status === 'differs' ? ' diff' : '')} role="row" key={c.id}>
                <span role="cell">{c.label}</span>
                <span className="m" role="cell">
                  {c.expected}
                </span>
                <span className="m py" role="cell">
                  <b>{c.actual}</b>
                </span>
                <span className="res" role="cell">
                  <i></i>
                  <em style={{ fontStyle: 'normal' }}>{c.status === 'differs' ? 'Differs' : 'Match'}</em>
                </span>
                <span className="delta">{c.status === 'differs' && c.delta ? c.delta : ''}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="compare static">
        <CodePanel index={5} name={rep.program.filename} label="Original" lang={rep.program.lang} lines={rep.code.original.split('\n')} flags={new Map()} fresh={new Set()} groupKey="x" />
        <CodePanel index={6} name={name + '.py'} label="Translated" lang="py" lines={rep.code.python.split('\n')} flags={new Map()} fresh={new Set()} groupKey="x" />
      </div>
    </>
  )
}
