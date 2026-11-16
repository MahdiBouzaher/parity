import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { RunEvent } from '../api/types'
import { Button } from '../components/Button'
import { ErrorPanel } from '../components/ErrorPanel'
import { Panel } from '../components/Panel'
import { ProgressBar } from '../components/ProgressBar'
import { PythonOutput } from '../components/PythonOutput'
import { StepList, type StepView } from '../components/StepList'
import { baseName, sv } from '../lib/format'
import { prefersReducedMotion, usePacedQueue } from '../lib/hooks'
import { nav } from '../state/router'
import { fileNameOf, useStore } from '../state/store'

const LABELS = ['Parsed original', 'Translated to pandas', 'Running on your data', 'Comparing outputs', 'Writing report']

const blank = (): StepView[] => LABELS.map((label) => ({ label, state: '', detail: '' }))

interface ErrInfo {
  message: string
  stderr: string
}

export function RunningScreen({ id }: { id: string }) {
  const { state, toast } = useStore()
  const [steps, setSteps] = useState<StepView[]>(blank)
  const [percent, setPercent] = useState(0)
  const [sub, setSub] = useState(0)
  const [text, setText] = useState('')
  const [status, setStatus] = useState('waiting')
  const [title, setTitle] = useState(fileNameOf(state))
  const [err, setErr] = useState<ErrInfo | null>(null)
  const textRef = useRef('')
  const lastStep = useRef(0)
  const linesKnown = useRef(false)
  const left = useRef(false)

  const push = usePacedQueue<RunEvent>(async (e, ctx) => {
    const reduced = prefersReducedMotion()
    if (e.name === 'run') {
      setTitle(e.data.filename)
      return
    }
    if (e.name === 'notice') {
      toast(e.data.message)
      return
    }
    if (e.name === 'step') {
      const gap = reduced ? 0 : 450 - (Date.now() - lastStep.current)
      if (gap > 0) await ctx.sleep(gap)
      if (!ctx.alive()) return
      lastStep.current = Date.now()
      const { index, state: st, detail, percent: p } = e.data
      setSteps((prev) =>
        prev.map((s, i) => {
          if (i !== index) return s
          const keep = !detail || (index === 1 && linesKnown.current)
          return { ...s, state: st === 'error' ? '' : st, detail: keep ? s.detail : detail }
        })
      )
      setPercent(p)
      if (st === 'active') setSub(index)
      if (index === 1 && st === 'active') setStatus('writing')
      return
    }
    if (e.name === 'python') {
      setStatus('writing')
      const chunk = e.data.chunk
      if (reduced) {
        textRef.current += chunk
        setText(textRef.current)
        return
      }
      let i = 0
      while (i < chunk.length) {
        const n = 1 + Math.floor(Math.random() * 3)
        textRef.current += chunk.slice(i, i + n)
        i += n
        setText(textRef.current)
        await ctx.sleep(13 + Math.random() * 16)
        if (!ctx.alive()) return
      }
      return
    }
    if (e.name === 'python_done') {
      linesKnown.current = true
      setSteps((prev) => prev.map((s, i) => (i === 1 ? { ...s, detail: `${e.data.lines} lines` } : s)))
      setStatus('done')
      return
    }
    if (e.name === 'done') {
      await ctx.sleep(reduced ? 0 : 550)
      if (ctx.alive() && !left.current) nav('/report/' + id)
      return
    }
    if (e.name === 'error') {
      setErr({ message: e.data.message, stderr: e.data.stderr })
      return
    }
    if (e.name === 'cancelled') {
      if (!left.current) nav('/')
    }
  })

  const cancel = () => {
    left.current = true
    api.cancelRun(id).catch(() => undefined)
    nav('/')
  }

  useEffect(() => {
    const close = api.streamRun(id, push, () =>
      push({
        name: 'error',
        data: { step: 'run', message: 'The connection closed before the run finished.', stderr: '' }
      })
    )
    const key = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName ?? ''
      if (tag === 'TEXTAREA' || tag === 'INPUT' || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'Escape') cancel()
    }
    window.addEventListener('keydown', key)
    return () => {
      left.current = true
      close()
      window.removeEventListener('keydown', key)
    }
  }, [id])

  return (
    <>
      <h2 className="run-title rise" style={sv({ '--i': 0 })}>
        {err ? 'Run failed' : `Translating ${title}`}
      </h2>
      {err ? null : (
        <p className="run-sub rise" style={sv({ '--i': 1 })}>
          Step {sub + 1} of 5
        </p>
      )}
      {err ? <div style={{ height: 24 }}></div> : <ProgressBar percent={percent} index={2} />}
      {err ? (
        <ErrorPanel title="The Python did not run" message={err.message} stderr={err.stderr} onBack={() => nav('/')} index={3} />
      ) : (
        <div className="run-grid">
          <Panel className="rise" style={sv({ '--i': 3 })}>
            <StepList steps={steps} />
          </Panel>
          <PythonOutput name={baseName(title) + '.py'} status={status} text={text} caret={status === 'writing'} index={4} />
        </div>
      )}
      {err ? null : (
        <div className="run-foot rise" style={sv({ '--i': 5 })}>
          <span>The Python runs on your uploaded input. Your original file is not changed.</span>
          <Button size="sm" onClick={cancel}>
            Cancel
          </Button>
        </div>
      )}
    </>
  )
}
