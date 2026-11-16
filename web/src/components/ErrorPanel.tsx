import { sv } from '../lib/format'
import { Button } from './Button'

interface Props {
  title: string
  message: string
  stderr?: string
  onBack: () => void
  index: number
}

export function ErrorPanel({ title, message, stderr, onBack, index }: Props) {
  return (
    <div className="panel err rise" style={sv({ '--i': index })}>
      <h3>{title}</h3>
      <p>{message}</p>
      {stderr ? <pre>{stderr}</pre> : <div style={{ height: 22 }}></div>}
      <Button onClick={onBack}>Back</Button>
    </div>
  )
}
