import type { CSSProperties, ReactNode } from 'react'

interface Props {
  className?: string
  style?: CSSProperties
  children: ReactNode
}

export function Panel({ className, style, children }: Props) {
  return (
    <div className={'panel' + (className ? ' ' + className : '')} style={style}>
      {children}
    </div>
  )
}
