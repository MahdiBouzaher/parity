import { useCallback, useEffect, useRef, useState } from 'react'

export const prefersReducedMotion = (): boolean =>
  typeof window !== 'undefined' && !!window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(prefersReducedMotion)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const on = () => setReduced(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return reduced
}

interface CountOptions {
  dur?: number
  firstDur?: number
  delay?: number
}

export function useCountUp(to: number, o: CountOptions = {}): number {
  const [v, setV] = useState(0)
  const cur = useRef(0)
  const first = useRef(true)

  useEffect(() => {
    const isFirst = first.current
    first.current = false
    const dur = isFirst ? (o.firstDur ?? o.dur ?? 900) : (o.dur ?? 900)
    const delay = isFirst ? (o.delay ?? 0) : 0
    const from = cur.current
    if (prefersReducedMotion() || from === to || dur <= 0) {
      cur.current = to
      setV(to)
      return
    }
    let raf = 0
    let timer = 0
    const run = () => {
      const t0 = performance.now()
      const step = (t: number) => {
        const p = Math.min(1, (t - t0) / dur)
        const e = 1 - Math.pow(1 - p, 3)
        const val = from + (to - from) * e
        cur.current = val
        setV(val)
        if (p < 1) raf = requestAnimationFrame(step)
      }
      raf = requestAnimationFrame(step)
    }
    if (delay > 0) timer = window.setTimeout(run, delay)
    else run()
    return () => {
      cancelAnimationFrame(raf)
      clearTimeout(timer)
    }
  }, [to])

  return v
}

export interface QueueCtx {
  alive: () => boolean
  sleep: (ms: number) => Promise<void>
}

interface Pending {
  t: number
  res: () => void
}

export class PacedQueue<T> {
  private items: T[] = []
  private busy = false
  private dead = false
  private pending = new Set<Pending>()
  private handle: (item: T, ctx: QueueCtx) => Promise<void>

  constructor(handle: (item: T, ctx: QueueCtx) => Promise<void>) {
    this.handle = handle
  }

  private ctx: QueueCtx = {
    alive: () => !this.dead,
    sleep: (ms) =>
      new Promise<void>((res) => {
        if (this.dead || ms <= 0) {
          res()
          return
        }
        const entry: Pending = { t: 0, res }
        entry.t = window.setTimeout(() => {
          this.pending.delete(entry)
          res()
        }, ms)
        this.pending.add(entry)
      })
  }

  push(item: T): void {
    if (this.dead) return
    this.items.push(item)
    void this.drain()
  }

  stop(): void {
    this.dead = true
    this.items = []
    this.pending.forEach((p) => {
      clearTimeout(p.t)
      p.res()
    })
    this.pending.clear()
  }

  private async drain(): Promise<void> {
    if (this.busy) return
    this.busy = true
    while (this.items.length && !this.dead) {
      const item = this.items.shift() as T
      try {
        await this.handle(item, this.ctx)
      } catch {
        continue
      }
    }
    this.busy = false
  }
}

export function usePacedQueue<T>(handle: (item: T, ctx: QueueCtx) => Promise<void>): (item: T) => void {
  const latest = useRef(handle)
  latest.current = handle
  const q = useRef<PacedQueue<T> | null>(null)
  if (!q.current) q.current = new PacedQueue<T>((i, c) => latest.current(i, c))
  useEffect(() => () => q.current?.stop(), [])
  return useCallback((e: T) => q.current?.push(e), [])
}
