import { Fragment, useLayoutEffect, useRef } from 'react'
import { sv } from '../lib/format'
import { Hl } from './Hl'

interface Props {
  name: string
  status: string
  text: string
  caret: boolean
  index: number
}

export function PythonOutput({ name, status, text, caret, index }: Props) {
  const ref = useRef<HTMLPreElement>(null)
  useLayoutEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [text])
  const lines = text === '' ? [] : text.split('\n')
  return (
    <div className="panel outp rise" style={sv({ '--i': index })}>
      <div className="phead">
        <span>{name}</span>
        <small>{status}</small>
      </div>
      <pre aria-label="Generated Python" ref={ref}>
        {lines.map((l, i) => (
          <Fragment key={i}>
            <Hl line={l} lang="py" />
            {i < lines.length - 1 ? '\n' : ''}
          </Fragment>
        ))}
        {caret && <span className="caret"></span>}
      </pre>
    </div>
  )
}
