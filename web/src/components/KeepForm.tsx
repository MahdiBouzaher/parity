import { useEffect, useRef, useState } from 'react'
import { Button } from './Button'

interface Props {
  busy: boolean
  onSubmit: (reason: string) => void
  onCancel: () => void
}

export function KeepForm({ busy, onSubmit, onCancel }: Props) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)
  const ok = text.trim().length > 0

  useEffect(() => {
    ref.current?.focus()
  }, [])

  const submit = () => {
    if (ok && !busy) onSubmit(text.trim())
  }

  return (
    <div className="kform">
      <label htmlFor="keep-reason">Why is this difference acceptable?</label>
      <textarea
        id="keep-reason"
        className="kin"
        ref={ref}
        value={text}
        maxLength={1000}
        rows={3}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submit()
          } else if (e.key === 'Escape') {
            e.preventDefault()
            onCancel()
          }
        }}
      />
      <div className="krow">
        <Button variant="primary" onClick={submit} loading={busy} disabled={!ok}>
          Keep difference
        </Button>
        <Button onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
