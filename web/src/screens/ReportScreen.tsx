import { useRef, useState } from 'react'
import { api, errorMessage } from '../api'
import type { Explanation, Run } from '../api/types'
import { Button } from '../components/Button'
import { Chip } from '../components/Chip'
import { ChecksTable } from '../components/ChecksTable'
import { CodePanel, type LineFlag } from '../components/CodePanel'
import { ErrorPanel } from '../components/ErrorPanel'
import { Summary, type SegState } from '../components/Summary'
import { WhyCard } from '../components/WhyCard'
import { baseName, plural, sv } from '../lib/format'
import { nav } from '../state/router'
import { useRun } from '../state/useRun'
import { useStore } from '../state/store'

const NONE: Explanation = {
  source: 'none',
  tag: null,
  title: 'No explanation available',
  paragraphs: [],
  note: 'Only the numbers that differ are shown.',
  fixed_body: ''
}

function ReportView({ run, onRun }: { run: Run; onRun: (r: Run) => void }) {
  const { toast } = useStore()
  const [animate, setAnimate] = useState(false)
  const [busy, setBusy] = useState<'fix' | 'keep' | 'undo' | null>(null)
  const last = useRef<Explanation | null>(null)

  const cur = run.current
  const state = run.state
  const fixed = state === 'fixed'
  const kept = state === 'kept'
  if (cur.explanation) last.current = cur.explanation
  const explanation = cur.explanation ?? (state === 'differs' ? NONE : last.current ?? NONE)
  const tag = cur.explanation?.tag ?? last.current?.tag ?? null
  const base = baseName(run.filename)
  const label = run.lang === 'sas' ? 'SAS' : 'VBA'
  const total = cur.summary.total
  const differs = cur.checks.filter((c) => c.status === 'differs').length

  const chipVariant = fixed || state === 'match' ? 'ok' : kept ? 'kept' : 'warn'
  const chipText =
    fixed || state === 'match'
      ? 'All checks match'
      : kept
        ? plural(differs, 'accepted difference', 'accepted differences')
        : plural(differs, 'difference', 'differences')

  const segments: SegState[] = cur.checks.map((c) => (c.status === 'differs' ? (kept ? 'kept' : 'warn') : 'ok'))

  const flagsFor = (lines: Run['risky_source'], tagText: (t: string) => string) => {
    const m = new Map<number, LineFlag>()
    if (state === 'match' || (!tag && !fixed)) return m
    lines
      .filter((r) => !tag || r.tag === tag)
      .forEach((r) => m.set(r.line, { cls: fixed ? 'fixed' : 'flag', tag: tagText(r.tag) }))
    return m
  }
  const srcFlags = flagsFor(run.risky_source, (t) => (fixed ? '' : t))
  const pyFlags = flagsFor(cur.risky_python, (t) => (fixed ? 'fixed' : t))
  if (fixed && pyFlags.size === 0) cur.changed_lines.forEach((n) => pyFlags.set(n, { cls: 'fixed', tag: 'fixed' }))
  const fresh = new Set<number>(animate && fixed ? cur.changed_lines : [])
  const groupKey = `${cur.index}-${state}`

  const act = async (kind: 'fix' | 'keep' | 'undo') => {
    setBusy(kind)
    try {
      const next =
        kind === 'fix' ? await api.fixRun(run.id) : kind === 'keep' ? await api.keepRun(run.id) : await api.undoRun(run.id)
      setAnimate(true)
      onRun(next)
    } catch (e) {
      toast(errorMessage(e))
    }
    setBusy(null)
  }

  return (
    <>
      <p className="crumb rise" style={sv({ '--i': 0 })}>
        Reports&nbsp; /&nbsp; {base}
      </p>
      <div className="rhead rise" style={sv({ '--i': 1 })}>
        <div className="rtitle">
          <h2>{run.filename}</h2>
          <Chip variant={chipVariant} text={chipText} />
        </div>
        <div className="ractions">
          <Button onClick={() => nav('/export/' + run.id)}>Export report</Button>
          <a className="btn primary" href={api.pythonUrl(run.id)} download={base + '.py'}>
            Download .py
          </a>
        </div>
      </div>
      <Summary
        index={2}
        matched={cur.summary.matched}
        total={total}
        segments={segments}
        rows={cur.summary.rows_compared}
        seconds={cur.summary.run_seconds}
        tolerance={cur.summary.tolerance}
      />
      <div className={'compare' + (animate ? ' static' : '')}>
        <CodePanel
          index={3}
          name={run.filename}
          label="Original"
          lang={run.lang}
          lines={run.source.split('\n')}
          flags={srcFlags}
          fresh={new Set()}
          groupKey={groupKey}
        />
        <CodePanel
          index={4}
          name={base + '.py'}
          label="Translated"
          lang="py"
          lines={cur.python.split('\n')}
          flags={pyFlags}
          fresh={fresh}
          groupKey={groupKey}
        />
      </div>
      <ChecksTable index={5} checks={cur.checks} runId={run.id} sourceLabel={label} animate={animate} />
      <WhyCard
        key={groupKey}
        index={6}
        state={state}
        total={total}
        explanation={explanation}
        fixedBody={last.current?.fixed_body || `All ${total} checks match. The translation now gives the same output as the original.`}
        canFix={cur.patch !== null && explanation.source !== 'none'}
        busy={busy}
        swap={animate}
        onFix={() => act('fix')}
        onKeep={() => act('keep')}
        onUndo={() => act('undo')}
      />
    </>
  )
}

export function ReportScreen({ id }: { id: string }) {
  const { run, setRun, error } = useRun(id)

  if (error) {
    return (
      <div style={{ marginTop: 56 }}>
        <ErrorPanel title="This report is not available" message={error} onBack={() => nav('/')} index={0} />
      </div>
    )
  }
  if (!run) return null
  if (run.status === 'failed' || run.status === 'cancelled') {
    return (
      <div style={{ marginTop: 56 }}>
        <ErrorPanel
          title="The Python did not run"
          message={run.error ? run.error.message : 'This run did not finish.'}
          stderr={run.error?.stderr}
          onBack={() => nav('/')}
          index={0}
        />
      </div>
    )
  }
  return <ReportView key={run.id} run={run} onRun={setRun} />
}
