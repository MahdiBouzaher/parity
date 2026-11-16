import { useEffect, useState } from 'react'
import { api, errorMessage, type Run } from '../api'

export function useRun(id: string) {
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setRun(null)
    setError(null)
    api
      .getRun(id)
      .then((r) => {
        if (live) setRun(r)
      })
      .catch((e) => {
        if (live) setError(errorMessage(e))
      })
    return () => {
      live = false
    }
  }, [id])

  return { run, setRun, error }
}
