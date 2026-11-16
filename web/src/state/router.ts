import { useEffect, useSyncExternalStore } from 'react'

export type RouteName = 'translate' | 'data' | 'running' | 'report' | 'history' | 'export'

export interface Route {
  name: RouteName
  id?: string
}

const subscribe = (cb: () => void) => {
  window.addEventListener('hashchange', cb)
  return () => window.removeEventListener('hashchange', cb)
}

const snapshot = () => window.location.hash

export function parseHash(hash: string): Route | null {
  const path = hash.replace(/^#/, '')
  const parts = path.split('/').filter(Boolean)
  if (parts.length === 0) return { name: 'translate' }
  const [head, id] = parts
  if (parts.length === 1 && head === 'data') return { name: 'data' }
  if (parts.length === 1 && head === 'history') return { name: 'history' }
  if (parts.length === 2 && head === 'running') return { name: 'running', id }
  if (parts.length === 2 && head === 'report') return { name: 'report', id }
  if (parts.length === 2 && head === 'export') return { name: 'export', id }
  return null
}

export function viewKey(r: Route): string {
  if (r.name === 'running' || r.name === 'report') return `${r.name}:${r.id}`
  if (r.name === 'export' && r.id) return `export:${r.id}`
  return r.name
}

export function nav(path: string): void {
  const h = '#' + path
  if (window.location.hash !== h) window.location.hash = h
}

export function useHash(): string {
  const hash = useSyncExternalStore(subscribe, snapshot)
  useEffect(() => {
    if (parseHash(hash) === null) window.location.replace('#/')
  }, [hash])
  return hash
}
