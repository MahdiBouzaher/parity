import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, type Dispatch, type ReactNode } from 'react'
import { api } from '../api'
import { SAMPLES, canned } from '../api/canned'
import type { Dataset, Health, Lang } from '../api/types'

interface State {
  lang: Lang
  source: string
  filename: string | null
  datasetId: string | null
  dataset: Dataset | null
  health: Health | null
  samples: Record<Lang, string>
  toast: { id: number; msg: string } | null
}

type Action =
  | { type: 'lang'; lang: Lang; sample: boolean }
  | { type: 'source'; source: string; lang?: Lang }
  | { type: 'file'; source: string; lang: Lang; filename: string }
  | { type: 'dataset'; dataset: Dataset | null }
  | { type: 'health'; health: Health }
  | { type: 'samples'; samples: Record<Lang, string> }
  | { type: 'toast'; msg: string }

const KEYS = {
  source: 'parity.source',
  lang: 'parity.lang',
  filename: 'parity.filename',
  dataset: 'parity.dataset'
}

function read(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) window.sessionStorage.removeItem(key)
    else window.sessionStorage.setItem(key, value)
  } catch {
    return
  }
}

function init(): State {
  const lang: Lang = read(KEYS.lang) === 'vba' ? 'vba' : 'sas'
  const stored = read(KEYS.source)
  return {
    lang,
    source: stored ?? SAMPLES[lang],
    filename: read(KEYS.filename),
    datasetId: read(KEYS.dataset),
    dataset: null,
    health: null,
    samples: SAMPLES,
    toast: null
  }
}

function reducer(s: State, a: Action): State {
  switch (a.type) {
    case 'lang':
      return a.sample ? { ...s, lang: a.lang, source: s.samples[a.lang], filename: null } : { ...s, lang: a.lang }
    case 'source':
      return { ...s, source: a.source, lang: a.lang ?? s.lang }
    case 'file':
      return { ...s, source: a.source, lang: a.lang, filename: a.filename }
    case 'dataset':
      return { ...s, dataset: a.dataset, datasetId: a.dataset ? a.dataset.id : null }
    case 'health':
      return { ...s, health: a.health }
    case 'samples': {
      const untouched = s.filename === null && s.source === s.samples[s.lang]
      return { ...s, samples: a.samples, source: untouched ? a.samples[s.lang] : s.source }
    }
    case 'toast':
      return { ...s, toast: { id: (s.toast?.id ?? 0) + 1, msg: a.msg } }
  }
}

interface Store {
  state: State
  dispatch: Dispatch<Action>
  toast: (msg: string) => void
}

const Ctx = createContext<Store | null>(null)

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, init)

  useEffect(() => {
    write(KEYS.source, state.source)
    write(KEYS.lang, state.lang)
    write(KEYS.filename, state.filename)
    write(KEYS.dataset, state.datasetId)
  }, [state.source, state.lang, state.filename, state.datasetId])

  useEffect(() => {
    api
      .health()
      .then((health) => dispatch({ type: 'health', health }))
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    api
      .samples()
      .then((list) => {
        const samples = { ...SAMPLES }
        list.forEach((x) => {
          samples[x.lang] = x.source
        })
        dispatch({ type: 'samples', samples })
      })
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!state.datasetId || state.dataset) return
    api
      .getDataset(state.datasetId)
      .then((dataset) => dispatch({ type: 'dataset', dataset }))
      .catch(() => dispatch({ type: 'dataset', dataset: null }))
  }, [state.datasetId, state.dataset])

  const toast = useCallback((msg: string) => dispatch({ type: 'toast', msg }), [])
  const value = useMemo(() => ({ state, dispatch, toast }), [state, toast])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useStore(): Store {
  const v = useContext(Ctx)
  if (!v) throw new Error('Store is missing')
  return v
}

export const fileNameOf = (s: Pick<State, 'lang' | 'filename'>): string => s.filename ?? canned[s.lang].file
