import { useEffect, useState } from 'react'
import { useStore } from '../state/store'

export function Toast() {
  const { state } = useStore()
  const [show, setShow] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    if (!state.toast) return
    setMsg(state.toast.msg)
    setShow(true)
    const t = window.setTimeout(() => setShow(false), 2400)
    return () => clearTimeout(t)
  }, [state.toast])

  return (
    <div className={'toast' + (show ? ' show' : '')} role="status" aria-live="polite">
      {msg}
    </div>
  )
}
