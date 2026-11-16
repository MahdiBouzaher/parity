export function Chip({ variant, text }: { variant: 'warn' | 'ok' | 'kept'; text: string }) {
  const cls = 'chip' + (variant === 'ok' ? ' ok' : variant === 'kept' ? ' kept' : '')
  return (
    <span className={cls} aria-live="polite">
      <i></i>
      <span>{text}</span>
    </span>
  )
}
