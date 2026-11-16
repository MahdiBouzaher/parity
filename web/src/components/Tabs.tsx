import { useCallback, useEffect, useRef, useState } from 'react'

interface Item {
  id: string
  label: string
}

interface Props {
  items: Item[]
  value: string
  onChange: (id: string) => void
  label: string
}

export function Tabs({ items, value, onChange, label }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [pill, setPill] = useState({ w: 0, x: 0 })

  const measure = useCallback(() => {
    const el = ref.current?.querySelector<HTMLElement>('[aria-selected="true"]')
    if (!el || !el.offsetWidth) return
    setPill({ w: el.offsetWidth, x: el.offsetLeft })
  }, [])

  useEffect(() => {
    measure()
  }, [value, measure])

  useEffect(() => {
    let r2 = 0
    const r1 = requestAnimationFrame(() => {
      r2 = requestAnimationFrame(measure)
    })
    window.addEventListener('resize', measure)
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure)
    return () => {
      cancelAnimationFrame(r1)
      cancelAnimationFrame(r2)
      window.removeEventListener('resize', measure)
    }
  }, [measure])

  return (
    <div className="tabs" role="tablist" aria-label={label} ref={ref}>
      <i className="pill" style={{ width: pill.w, transform: `translateX(${pill.x}px)` }}></i>
      {items.map((it) => (
        <button
          key={it.id}
          className="tab"
          role="tab"
          id={`tab-${it.id}`}
          aria-selected={it.id === value}
          onClick={() => {
            if (it.id !== value) onChange(it.id)
          }}
        >
          {it.label}
        </button>
      ))}
    </div>
  )
}
