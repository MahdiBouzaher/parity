import { useEffect, useRef, useState, type ReactNode } from 'react'
import { prefersReducedMotion } from '../lib/hooks'
import { parseHash, viewKey, type Route } from '../state/router'

interface Props {
  hash: string
  render: (route: Route) => ReactNode
}

export function ViewHost({ hash, render }: Props) {
  const [shown, setShown] = useState(hash)
  const [out, setOut] = useState(false)
  const seq = useRef(0)

  useEffect(() => {
    const next = parseHash(hash)
    const cur = parseHash(shown)
    if (!next) return
    const s = ++seq.current
    if (cur && viewKey(cur) === viewKey(next)) {
      setShown(hash)
      setOut(false)
      return
    }
    setOut(true)
    const t = window.setTimeout(
      () => {
        if (s !== seq.current) return
        setShown(hash)
        setOut(false)
        window.scrollTo(0, 0)
      },
      prefersReducedMotion() ? 0 : 150
    )
    return () => clearTimeout(t)
  }, [hash])

  const route = parseHash(shown) ?? { name: 'translate' as const }
  return (
    <section className={'view' + (out ? ' out' : '')} key={viewKey(route)}>
      {render(route)}
    </section>
  )
}
