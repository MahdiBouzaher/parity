import { Fragment } from 'react'
import { tokenize, type HlLang } from '../lib/highlight'

export function Hl({ line, lang }: { line: string; lang: HlLang }) {
  return (
    <>
      {tokenize(line, lang).map((p, i) =>
        p.cls ? (
          <span key={i} className={p.cls}>
            {p.text}
          </span>
        ) : (
          <Fragment key={i}>{p.text}</Fragment>
        )
      )}
    </>
  )
}
