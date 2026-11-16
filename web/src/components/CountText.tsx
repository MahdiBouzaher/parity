import { useCountUp } from '../lib/hooks'
import { fmtDecimals } from '../lib/format'

interface Props {
  to: number
  decimals?: number
  prefix?: string
  suffix?: string
  dur?: number
  firstDur?: number
  delay?: number
}

export function CountText({ to, decimals = 0, prefix = '', suffix = '', dur, firstDur, delay }: Props) {
  const v = useCountUp(to, { dur, firstDur, delay })
  return (
    <>
      {prefix}
      {fmtDecimals(v, decimals)}
      {suffix}
    </>
  )
}
