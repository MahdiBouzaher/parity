import type { CSSProperties } from 'react'

export const fmt = (v: number): string => Math.round(v).toLocaleString('en-US')

export const fmtDecimals = (v: number, d: number): string =>
  v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })

export const fmtDelta = (v: number, d = 2): string => (v > 0 ? '+' : v < 0 ? '-' : '') + fmtDecimals(Math.abs(v), d)

export const baseName = (name: string): string => name.replace(/\.[^.]+$/, '')

export const sv = (vars: Record<string, string | number>): CSSProperties => vars as CSSProperties

export const plural = (n: number, one: string, many: string): string => `${n} ${n === 1 ? one : many}`
