import type { Lang } from '../api/types'

export const extOf = (name: string): string => (name.split('.').pop() || '').toLowerCase()

export const readText = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(String(r.result))
    r.onerror = () => reject(r.error)
    r.readAsText(file)
  })

export function detect(v: string): Lang | null {
  if (/\b(End\s+Sub|Sub\s+\w+\s*\(|Dim\s+\w+)/i.test(v)) return 'vba'
  if (/\b(proc\s+\w+|data\s+\w+\s*;|run\s*;)/i.test(v)) return 'sas'
  return null
}

export const langFromExt = (ext: string): Lang | null => (ext === 'bas' || ext === 'vba' || ext === 'cls' ? 'vba' : ext === 'sas' ? 'sas' : null)
