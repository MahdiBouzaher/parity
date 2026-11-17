import { useRef, useState } from 'react'

interface Props {
  label: string
  hint: string
  busy: boolean
  accept?: string
  busyLabel?: string
  onFile: (file: File) => void
}

export function DropZone({ label, hint, busy, accept = '.csv,text/csv', busyLabel = 'Uploading', onFile }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const [drag, setDrag] = useState(false)
  return (
    <>
      <button
        type="button"
        className={'drop' + (drag ? ' drag' : '')}
        disabled={busy}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setDrag(true)
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setDrag(false)
          const f = e.dataTransfer.files && e.dataTransfer.files[0]
          if (f) onFile(f)
        }}
      >
        <span>{busy ? busyLabel : label}</span>
        <small>{hint}</small>
      </button>
      <input
        ref={input}
        type="file"
        accept={accept}
        hidden
        aria-label={label}
        onChange={(e) => {
          const f = e.target.files && e.target.files[0]
          if (f) onFile(f)
          e.target.value = ''
        }}
      />
    </>
  )
}
