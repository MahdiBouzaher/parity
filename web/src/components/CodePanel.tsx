import { sv } from '../lib/format'
import type { HlLang } from '../lib/highlight'
import { Hl } from './Hl'

export interface LineFlag {
  cls: 'flag' | 'fixed'
  tag: string
}

interface Props {
  name: string
  label: string
  lang: HlLang
  lines: string[]
  flags: Map<number, LineFlag>
  fresh: Set<number>
  groupKey: string
  index: number
}

export function CodePanel({ name, label, lang, lines, flags, fresh, groupKey, index }: Props) {
  return (
    <div className="panel code rise" style={sv({ '--i': index })}>
      <div className="phead">
        <span>{name}</span>
        <small>{label}</small>
      </div>
      <div className="lines">
        {lines.map((l, k) => {
          const flag = flags.get(k + 1)
          const cls = 'ln' + (l === '' ? ' blank' : '') + (flag ? ' ' + flag.cls : '') + (fresh.has(k + 1) ? ' new' : '')
          return (
            <div key={`${groupKey}-${k}`} className={cls} style={sv({ '--k': k })}>
              <span className="tx">
                <Hl line={l} lang={lang} />
              </span>
              {flag && flag.tag && l.trim() !== '' ? <span className="tag">{flag.tag}</span> : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
