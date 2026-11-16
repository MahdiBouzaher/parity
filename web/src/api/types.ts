export type Lang = 'sas' | 'vba'

export interface RiskyLine {
  line: number
  tag: string
  reason: string
}

export interface Hunk {
  start: number
  remove: string[]
  add: string[]
}

export interface Patch {
  summary: string
  hunks: Hunk[]
}

export interface Explanation {
  source: 'model' | 'rules' | 'none'
  tag: string | null
  title: string
  paragraphs: string[]
  note: string
  fixed_body: string
}

export interface Mismatch {
  row: number
  column: string
  expected: string
  actual: string
}

export type CheckKind = 'rows' | 'columns' | 'stat' | 'cells'

export interface Check {
  id: string
  label: string
  kind: CheckKind
  table: string
  column: string | null
  status: 'match' | 'differs'
  expected: string
  actual: string
  tolerance: string
  delta: string | null
  details: string | null
  mismatch_count: number | null
  compared: number | null
  mismatches: Mismatch[]
}

export interface ColumnInfo {
  name: string
  dtype: 'int' | 'float' | 'text'
}

export interface DatasetFile {
  name: string
  rows: number
  sha256: string
  columns: ColumnInfo[]
  preview: (string | null)[][]
}

export interface ExpectedFile extends DatasetFile {
  table: string
}

export interface Dataset {
  id: string
  ready: boolean
  input: DatasetFile | null
  expected: ExpectedFile[]
  tolerances: Record<string, number>
}

export interface Summary {
  total: number
  matched: number
  differs: number
  rows_compared: number
  run_seconds: number
  tolerance: 'exact' | 'custom'
}

export interface Revision {
  index: number
  label: 'original' | 'fix'
  python_sha256: string
  matched: number
  total: number
}

export interface RunDataset {
  id: string
  input: { name: string; rows: number; sha256: string }
  expected: { table: string; name: string; rows: number; sha256: string }[]
  tolerances: Record<string, number>
}

export interface CurrentRevision {
  index: number
  label: 'original' | 'fix'
  python: string
  python_sha256: string
  risky_python: RiskyLine[]
  changed_lines: number[]
  checks: Check[]
  summary: Summary
  explanation: Explanation | null
  patch: Patch | null
}

export interface RunError {
  step: string
  message: string
  stderr?: string
}

export interface Run {
  id: string
  created_at: string
  lang: Lang
  filename: string
  status: 'running' | 'done' | 'failed' | 'cancelled'
  state: 'match' | 'differs' | 'fixed' | 'kept'
  source: string
  source_sha256: string
  dataset: RunDataset
  translation: { source: 'model' | 'rules'; model: string | null }
  risky_source: RiskyLine[]
  current: CurrentRevision
  revisions: Revision[]
  accepted: boolean
  error: RunError | null
}

export interface HistoryItem {
  id: string
  created_at: string
  filename: string
  lang: Lang
  status: Run['status']
  state: Run['state']
  matched: number
  total: number
  input_name: string
}

export interface HistoryPage {
  items: HistoryItem[]
  total: number
}

export interface Health {
  ok: boolean
  translation_model: { configured: boolean; name: string | null }
  python: string
  pandas: string
}

export interface SampleInfo {
  lang: Lang
  filename: string
  source: string
  input_name: string
  expected: string[]
}

export interface CreateRunBody {
  lang: Lang
  filename: string
  source: string
  dataset_id: string
}

export interface ExportReport {
  format: string
  version: number
  generated_at: string
  run_id: string
  program: { filename: string; lang: Lang }
  result: { state: Run['state']; matched: number; total: number; accepted_differences: string[] }
  translation: { source: 'model' | 'rules'; model: string | null; revisions: { index: number; label: string; python_sha256: string }[] }
  hashes: {
    original_code: string
    python: string
    input: { name: string; sha256: string }
    expected: { table: string; name: string; sha256: string }[]
  }
  tolerances: Record<string, number>
  checks: Check[]
  explanation: Explanation | null
  code: { original: string; python: string }
  report_sha256: string
}

export type StepKey = 'parse' | 'translate' | 'run' | 'compare' | 'report'

export type RunEvent =
  | { name: 'run'; data: { run_id: string; filename: string; lang: Lang; model_configured: boolean } }
  | { name: 'step'; data: { index: number; key: StepKey; state: 'active' | 'done' | 'error'; detail: string; percent: number } }
  | { name: 'risks'; data: { risky_lines: RiskyLine[] } }
  | { name: 'python'; data: { chunk: string } }
  | { name: 'python_done'; data: { lines: number; source: 'model' | 'rules' } }
  | { name: 'notice'; data: { code: 'no_key' | 'model_error'; message: string } }
  | { name: 'checks'; data: { total: number; matched: number; differs: number; rows_compared: number; run_seconds: number } }
  | { name: 'done'; data: { run_id: string; report: string; state: 'differs' | 'match'; matched: number; total: number } }
  | { name: 'error'; data: { step: string; message: string; stderr: string } }
  | { name: 'cancelled'; data: Record<string, never> }

export const EVENT_NAMES: RunEvent['name'][] = [
  'run',
  'step',
  'risks',
  'python',
  'python_done',
  'notice',
  'checks',
  'done',
  'error',
  'cancelled'
]

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export interface ParityApi {
  health(): Promise<Health>
  samples(): Promise<SampleInfo[]>
  createDataset(): Promise<Dataset>
  uploadInput(id: string, file: File): Promise<Dataset>
  uploadExpected(id: string, file: File, table?: string): Promise<Dataset>
  deleteExpected(id: string, table: string): Promise<Dataset>
  setTolerances(id: string, tolerances: Record<string, number>): Promise<Dataset>
  sampleDataset(lang: Lang): Promise<Dataset>
  getDataset(id: string): Promise<Dataset>
  createRun(body: CreateRunBody): Promise<{ run_id: string }>
  streamRun(id: string, onEvent: (e: RunEvent) => void, onClose: () => void): () => void
  cancelRun(id: string): Promise<{ ok: boolean }>
  getRun(id: string): Promise<Run>
  fixRun(id: string): Promise<Run>
  keepRun(id: string): Promise<Run>
  undoRun(id: string): Promise<Run>
  listRuns(limit?: number, offset?: number): Promise<HistoryPage>
  deleteRun(id: string): Promise<{ ok: boolean }>
  pythonUrl(id: string): string
  exportReport(id: string): Promise<ExportReport>
  exportUrl(id: string, kind: 'json' | 'html'): string
}
