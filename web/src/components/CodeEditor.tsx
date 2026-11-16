import { Fragment, useRef, type ReactNode } from 'react'
import type { Lang } from '../api/types'
import { sv } from '../lib/format'
import { Hl } from './Hl'
import { Tabs } from './Tabs'

interface Props {
  lang: Lang
  value: string
  drag: boolean
  onChange: (v: string) => void
  onLang: (l: Lang) => void
  onSubmit: () => void
  status: ReactNode
  action: ReactNode
  index: number
}

export function CodeEditor({ lang, value, drag, onChange, onLang, onSubmit, status, action, index }: Props) {
  const preRef = useRef<HTMLPreElement>(null)
  const gutRef = useRef<HTMLDivElement>(null)
  const lines = value.split('\n')

  return (
    <div className={'panel editor rise' + (drag ? ' drag' : '')} style={sv({ '--i': index })}>
      <div className="phead">
        <Tabs
          label="Source language"
          value={lang}
          onChange={(id) => onLang(id as Lang)}
          items={[
            { id: 'sas', label: 'SAS' },
            { id: 'vba', label: 'VBA' }
          ]}
        />
        <span className="hint">Paste code or drop a file</span>
      </div>
      <div className="ebody">
        <div className="gutter" aria-hidden="true" ref={gutRef}>
          {lines.map((_, i) => i + 1).join('\n')}
        </div>
        <div className="stack">
          <pre aria-hidden="true" ref={preRef}>
            {lines.map((l, i) => (
              <Fragment key={i}>
                <Hl line={l} lang={lang} />
                {'\n'}
              </Fragment>
            ))}
          </pre>
          <textarea
            spellCheck={false}
            autoComplete="off"
            autoCapitalize="off"
            aria-label="Source code"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onScroll={(e) => {
              const t = e.currentTarget
              if (preRef.current) {
                preRef.current.scrollTop = t.scrollTop
                preRef.current.scrollLeft = t.scrollLeft
              }
              if (gutRef.current) gutRef.current.scrollTop = t.scrollTop
            }}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault()
                onSubmit()
              }
            }}
          />
        </div>
      </div>
      <div className="efoot">
        <div className="status">{status}</div>
        {action}
      </div>
    </div>
  )
}
