import { http } from './http'
import { mock } from './mock'
import { ApiError, type ParityApi } from './types'

export const api: ParityApi = import.meta.env.VITE_API === 'mock' ? mock : http

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message
  return 'Something went wrong. Try again.'
}

export * from './types'
