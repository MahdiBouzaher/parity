import type { ButtonHTMLAttributes } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'primary'
  size?: 'md' | 'sm'
  loading?: boolean
}

export function Button({ variant = 'default', size = 'md', loading = false, className, children, disabled, ...rest }: Props) {
  const cls = ['btn', variant === 'primary' ? 'primary' : '', size === 'sm' ? 'sm' : '', className ?? '']
    .filter(Boolean)
    .join(' ')
  return (
    <button {...rest} className={cls} disabled={loading || disabled}>
      {loading && <i className="spin"></i>}
      {children}
    </button>
  )
}
