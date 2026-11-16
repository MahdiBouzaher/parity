import { EVENT_NAMES, type RunEvent } from './types'

const TERMINAL = ['done', 'error', 'cancelled']

export function openEvents(runId: string, onEvent: (e: RunEvent) => void, onClose: () => void): () => void {
  const es = new EventSource(`/api/runs/${runId}/events`)
  let finished = false

  EVENT_NAMES.forEach((name) => {
    es.addEventListener(name, (m) => {
      if (finished) return
      let data: unknown
      try {
        data = JSON.parse((m as MessageEvent).data)
      } catch {
        return
      }
      onEvent({ name, data } as RunEvent)
      if (TERMINAL.includes(name)) {
        finished = true
        es.close()
      }
    })
  })

  es.onerror = () => {
    if (finished) return
    if (es.readyState === EventSource.CLOSED) {
      finished = true
      onClose()
    }
  }

  return () => {
    finished = true
    es.close()
  }
}
