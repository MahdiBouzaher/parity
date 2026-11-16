import { useCallback, useEffect, useState } from 'react'
import { api, errorMessage, type HistoryItem } from '../api'

export function useHistory() {
  const [items, setItems] = useState<HistoryItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    api
      .listRuns()
      .then((p) => {
        if (live) setItems(p.items)
      })
      .catch((e) => {
        if (live) setError(errorMessage(e))
      })
    return () => {
      live = false
    }
  }, [])

  const remove = useCallback(async (id: string) => {
    await api.deleteRun(id)
    setItems((prev) => (prev ? prev.filter((x) => x.id !== id) : prev))
  }, [])

  return { items, error, remove }
}
