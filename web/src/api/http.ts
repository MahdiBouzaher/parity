import {
  ApiError,
  type CreateRunBody,
  type Dataset,
  type ExportReport,
  type Health,
  type HistoryPage,
  type Lang,
  type ParityApi,
  type Run,
  type SampleInfo
} from './types'
import { openEvents } from './sse'

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let code = 'bad_request'
    let message = 'The request failed.'
    try {
      const j = await res.json()
      if (j && j.error) {
        code = j.error.code
        message = j.error.message
      }
    } catch {
      message = 'The server did not respond as expected.'
    }
    throw new ApiError(res.status, code, message)
  }
  return (await res.json()) as T
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method }
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }
  let res: Response
  try {
    res = await fetch('/api' + path, init)
  } catch {
    throw new ApiError(0, 'network', 'The server is not reachable.')
  }
  return handle<T>(res)
}

async function upload<T>(method: string, path: string, file: File, table?: string): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  if (table) form.append('table', table)
  let res: Response
  try {
    res = await fetch('/api' + path, { method, body: form })
  } catch {
    throw new ApiError(0, 'network', 'The server is not reachable.')
  }
  return handle<T>(res)
}

export const http: ParityApi = {
  health: () => req<Health>('GET', '/health'),
  samples: () => req<SampleInfo[]>('GET', '/samples'),
  createDataset: () => req<Dataset>('POST', '/datasets', {}),
  uploadInput: (id, file) => upload<Dataset>('PUT', `/datasets/${id}/input`, file),
  uploadExpected: (id, file, table) => upload<Dataset>('POST', `/datasets/${id}/expected`, file, table),
  deleteExpected: (id, table) => req<Dataset>('DELETE', `/datasets/${id}/expected/${encodeURIComponent(table)}`),
  setTolerances: (id, tolerances) => req<Dataset>('PUT', `/datasets/${id}/tolerances`, { tolerances }),
  sampleDataset: (lang: Lang) => req<Dataset>('POST', '/datasets/sample', { lang }),
  getDataset: (id) => req<Dataset>('GET', `/datasets/${id}`),
  createRun: (body: CreateRunBody) => req<{ run_id: string }>('POST', '/runs', body),
  streamRun: (id, onEvent, onClose) => openEvents(id, onEvent, onClose),
  cancelRun: (id) => req<{ ok: boolean }>('POST', `/runs/${id}/cancel`),
  getRun: (id) => req<Run>('GET', `/runs/${id}`),
  fixRun: (id) => req<Run>('POST', `/runs/${id}/fix`),
  keepRun: (id) => req<Run>('POST', `/runs/${id}/keep`),
  undoRun: (id) => req<Run>('POST', `/runs/${id}/undo`),
  listRuns: (limit = 50, offset = 0) => req<HistoryPage>('GET', `/runs?limit=${limit}&offset=${offset}`),
  deleteRun: (id) => req<{ ok: boolean }>('DELETE', `/runs/${id}`),
  pythonUrl: (id) => `/api/runs/${id}/python`,
  exportReport: (id) => req<ExportReport>('GET', `/runs/${id}/export`),
  exportUrl: (id, kind) => `/api/runs/${id}/export.${kind}`
}
