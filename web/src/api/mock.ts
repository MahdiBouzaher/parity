import { prefersReducedMotion } from '../lib/hooks'
import { PREVIEW_INPUT, ROWS_TOTAL, RUN_SECONDS, SAMPLES, canned } from './canned'
import {
  ApiError,
  type Check,
  type CreateRunBody,
  type Dataset,
  type DatasetFile,
  type Explanation,
  type ExportReport,
  type HistoryItem,
  type Lang,
  type ParityApi,
  type RiskyLine,
  type Run,
  type RunEvent,
  type VerifyResult
} from './types'

type Mode = 'differs' | 'fixed' | 'kept'

interface Rec {
  id: string
  lang: Lang
  filename: string
  source: string
  created_at: string
  mode: Mode
  reason: string | null
}

const runs = new Map<string, Rec>()
const datasets = new Map<string, Dataset>()

const scale = () => (prefersReducedMotion() ? 0.12 : 1)
const wait = (ms: number) => new Promise<void>((res) => setTimeout(res, ms))

const hex = (n: number) =>
  Array.from({ length: n }, () => Math.floor(Math.random() * 16).toString(16)).join('')

const fakeHash = (seed: string) => {
  let out = ''
  let h = 2166136261
  for (let i = 0; out.length < 64; i++) {
    h ^= seed.charCodeAt(i % seed.length) + i
    h = Math.imul(h, 16777619) >>> 0
    out += h.toString(16).padStart(8, '0')
  }
  return out.slice(0, 64)
}

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')

function loansFile(): DatasetFile {
  return {
    name: 'loans.csv',
    rows: ROWS_TOTAL,
    sha256: fakeHash('loans.csv'),
    columns: [
      { name: 'loan_id', dtype: 'int' },
      { name: 'segment', dtype: 'text' },
      { name: 'exposure', dtype: 'float' },
      { name: 'balance', dtype: 'float' },
      { name: 'pd', dtype: 'float' },
      { name: 'lgd', dtype: 'float' }
    ],
    preview: PREVIEW_INPUT
  }
}

function sampleDataset(lang: Lang): Dataset {
  const c = canned[lang]
  const input = loansFile()
  return {
    id: hex(12),
    ready: true,
    input,
    expected: [
      {
        table: c.table,
        name: `${c.table}.csv`,
        rows: ROWS_TOTAL,
        sha256: fakeHash(c.table),
        columns: [...input.columns, { name: 'rate', dtype: 'float' }, { name: 'prov', dtype: 'float' }],
        preview: PREVIEW_INPUT.map((r) => [...r, '0.0063', '157.50'])
      }
    ],
    tolerances: {}
  }
}

function checksFor(lang: Lang, fixed: boolean): Check[] {
  const c = canned[lang]
  return c.checks.map((k, i) => {
    const isDiff = i === c.diffIndex && !fixed
    return {
      id: `${c.table}.${k.kind}.${slug(k.label)}`,
      label: k.label,
      kind: k.kind,
      table: c.table,
      column: null,
      status: isDiff ? 'differs' : 'match',
      expected: k.expected,
      actual: i === c.diffIndex && fixed ? k.expected : k.actual,
      tolerance: 'exact',
      delta: isDiff ? k.delta : null,
      details: i === c.diffIndex ? k.details : null,
      mismatch_count: null,
      compared: null,
      mismatches: []
    }
  })
}

function explanationFor(lang: Lang): Explanation {
  const c = canned[lang]
  return {
    source: 'rules',
    tag: c.tag,
    title: c.whyTitle,
    paragraphs: c.whyBody,
    note: c.whyNote,
    fixed_body: c.fixedBody
  }
}

function buildRun(r: Rec): Run {
  const c = canned[r.lang]
  const fixed = r.mode === 'fixed'
  const total = c.checks.length
  const matched = fixed ? total : total - 1
  const lines = fixed ? c.pyAfter : c.pyBefore
  const python = lines.join('\n')
  const risk = (line: number): RiskyLine => ({ line, tag: c.tag, reason: c.reason })
  const input = loansFile()
  const revisions: Run['revisions'] = [
    { index: 0, label: 'original', python_sha256: fakeHash(c.pyBefore.join('\n')), matched: total - 1, total }
  ]
  if (fixed) {
    revisions.push({ index: 1, label: 'fix', python_sha256: fakeHash(python), matched: total, total })
  }
  return {
    id: r.id,
    created_at: r.created_at,
    lang: r.lang,
    filename: r.filename,
    status: 'done',
    state: r.mode,
    source: r.source,
    source_sha256: fakeHash(r.source),
    dataset: {
      id: hex(12),
      input: { name: input.name, rows: input.rows, sha256: input.sha256 },
      expected: [{ table: c.table, name: `${c.table}.csv`, rows: ROWS_TOTAL, sha256: fakeHash(c.table) }],
      tolerances: {}
    },
    translation: { source: 'rules', model: null },
    risky_source: [risk(c.srcFlag)],
    current: {
      index: fixed ? 1 : 0,
      label: fixed ? 'fix' : 'original',
      python,
      python_sha256: fakeHash(python),
      risky_python: [risk(fixed ? c.flagAfter : c.flagBefore)],
      changed_lines: fixed ? c.changed : [],
      checks: checksFor(r.lang, fixed),
      summary: {
        total,
        matched,
        differs: total - matched,
        rows_compared: ROWS_TOTAL,
        run_seconds: RUN_SECONDS,
        tolerance: 'exact'
      },
      explanation: fixed ? null : explanationFor(r.lang),
      patch: fixed
        ? null
        : {
            summary: c.whyNote,
            hunks: [{ start: c.flagBefore, remove: [c.pyBefore[c.flagBefore - 1]], add: [c.pyAfter[c.flagAfter - 1]] }]
          }
    },
    revisions,
    accepted: r.mode === 'kept',
    keep_reason: r.mode === 'kept' ? r.reason : null,
    error: null
  }
}

function exportFor(r: Rec): ExportReport {
  const run = buildRun(r)
  const differing = run.current.checks.filter((c) => c.status === 'differs').map((c) => c.id)
  return {
    format: 'parity-report',
    version: 1,
    generated_at: new Date().toISOString(),
    signed_at: new Date().toISOString(),
    run_id: run.id,
    program: { filename: run.filename, lang: run.lang },
    result: {
      state: run.state,
      matched: run.current.summary.matched,
      total: run.current.summary.total,
      accepted_differences: run.state === 'kept' ? differing : [],
      keep_reason: run.state === 'kept' ? r.reason : null
    },
    translation: { source: 'rules', model: null, revisions: run.revisions.map((v) => ({ index: v.index, label: v.label, python_sha256: v.python_sha256 })) },
    hashes: {
      original_code: run.source_sha256,
      python: run.current.python_sha256,
      input: { name: run.dataset.input.name, sha256: run.dataset.input.sha256 },
      expected: run.dataset.expected.map((e) => ({ table: e.table, name: e.name, sha256: e.sha256 }))
    },
    tolerances: {},
    checks: run.current.checks,
    explanation: run.current.explanation,
    code: { original: run.source, python: run.current.python },
    report_sha256: fakeHash(run.id + run.state),
    signature: {
      algorithm: 'Ed25519',
      payload_sha256: fakeHash(run.id + run.state + 'payload'),
      signature: btoa(fakeHash(run.id + 'sig')),
      public_key: btoa(fakeHash('instance key')),
      key_fingerprint: fakeHash('instance key').slice(0, 16),
      signed_at: new Date().toISOString()
    }
  }
}

function recFor(id: string): Rec {
  const found = runs.get(id)
  if (found) return found
  const rec: Rec = {
    id,
    lang: 'sas',
    filename: canned.sas.file,
    source: SAMPLES.sas,
    created_at: new Date().toISOString(),
    mode: 'differs',
    reason: null
  }
  runs.set(id, rec)
  return rec
}

function stream(id: string, onEvent: (e: RunEvent) => void): () => void {
  const rec = recFor(id)
  const c = canned[rec.lang]
  const t = scale()
  const timers: number[] = []
  let at = 0
  const emit = (e: RunEvent) => {
    timers.push(window.setTimeout(() => onEvent(e), at * t))
  }
  const total = c.checks.length
  const nonblank = c.pyBefore.filter(Boolean).length

  emit({ name: 'run', data: { run_id: id, filename: rec.filename, lang: rec.lang, model_configured: false } })
  at = 650
  emit({ name: 'step', data: { index: 0, key: 'parse', state: 'active', detail: `${c.stmts} statements`, percent: 10 } })
  emit({
    name: 'risks',
    data: { risky_lines: [{ line: c.srcFlag, tag: c.tag, reason: c.reason }] }
  })
  at += 950
  emit({ name: 'step', data: { index: 0, key: 'parse', state: 'done', detail: `${c.stmts} statements`, percent: 20 } })
  emit({ name: 'step', data: { index: 1, key: 'translate', state: 'active', detail: '', percent: 30 } })
  c.pyBefore.forEach((line, i) => {
    emit({ name: 'python', data: { chunk: line + (i < c.pyBefore.length - 1 ? '\n' : '') } })
    at += 330
  })
  emit({ name: 'python_done', data: { lines: nonblank, source: 'rules' } })
  at += 250
  emit({ name: 'step', data: { index: 1, key: 'translate', state: 'done', detail: `${nonblank} lines`, percent: 40 } })
  emit({
    name: 'step',
    data: { index: 2, key: 'run', state: 'active', detail: `${ROWS_TOTAL.toLocaleString('en-US')} rows`, percent: 55 }
  })
  at += 1700
  emit({
    name: 'step',
    data: { index: 2, key: 'run', state: 'done', detail: `${ROWS_TOTAL.toLocaleString('en-US')} rows`, percent: 70 }
  })
  emit({ name: 'step', data: { index: 3, key: 'compare', state: 'active', detail: `${total} checks`, percent: 80 } })
  emit({
    name: 'checks',
    data: { total, matched: total - 1, differs: 1, rows_compared: ROWS_TOTAL, run_seconds: RUN_SECONDS }
  })
  at += 1100
  emit({ name: 'step', data: { index: 3, key: 'compare', state: 'done', detail: `${total} checks`, percent: 90 } })
  emit({ name: 'step', data: { index: 4, key: 'report', state: 'active', detail: '1 report', percent: 90 } })
  at += 750
  emit({ name: 'step', data: { index: 4, key: 'report', state: 'done', detail: '1 report', percent: 100 } })
  emit({
    name: 'done',
    data: { run_id: id, report: `/api/runs/${id}`, state: 'differs', matched: total - 1, total }
  })

  return () => {
    timers.forEach((x) => clearTimeout(x))
  }
}

function toItem(r: Rec): HistoryItem {
  const run = buildRun(r)
  return {
    id: r.id,
    created_at: r.created_at,
    filename: r.filename,
    lang: r.lang,
    status: 'done',
    state: run.state,
    matched: run.current.summary.matched,
    total: run.current.summary.total,
    input_name: 'loans.csv'
  }
}

export const mock: ParityApi = {
  health: async () => ({
    ok: true,
    translation_model: { configured: false, name: null },
    python: '3.12.1',
    pandas: '2.2.2'
  }),
  samples: async () =>
    (['sas', 'vba'] as Lang[]).map((lang) => ({
      lang,
      filename: canned[lang].file,
      source: SAMPLES[lang],
      input_name: 'loans.csv',
      expected: [`${canned[lang].table}.csv`]
    })),
  createDataset: async () => {
    const ds: Dataset = { id: hex(12), ready: false, input: null, expected: [], tolerances: {} }
    datasets.set(ds.id, ds)
    return ds
  },
  uploadInput: async (id, file) => {
    const ds = datasets.get(id)
    if (!ds) throw new ApiError(404, 'not_found', 'This dataset was not found.')
    const next: Dataset = { ...ds, input: { ...loansFile(), name: file.name } }
    next.ready = next.expected.length > 0
    datasets.set(id, next)
    return next
  },
  uploadExpected: async (id, file, table) => {
    const ds = datasets.get(id)
    if (!ds) throw new ApiError(404, 'not_found', 'This dataset was not found.')
    const name = table ?? file.name.replace(/\.[^.]+$/, '').toLowerCase().replace(/[^a-z0-9]+/g, '_')
    const sample = sampleDataset('sas').expected[0]
    const expected = [...ds.expected.filter((e) => e.table !== name), { ...sample, table: name, name: file.name }]
    const next: Dataset = { ...ds, expected, ready: ds.input !== null }
    datasets.set(id, next)
    return next
  },
  deleteExpected: async (id, table) => {
    const ds = datasets.get(id)
    if (!ds) throw new ApiError(404, 'not_found', 'This dataset was not found.')
    const expected = ds.expected.filter((e) => e.table !== table)
    const next: Dataset = { ...ds, expected, ready: ds.input !== null && expected.length > 0 }
    datasets.set(id, next)
    return next
  },
  setTolerances: async (id, tolerances) => {
    const ds = datasets.get(id)
    if (!ds) throw new ApiError(404, 'not_found', 'This dataset was not found.')
    const next: Dataset = { ...ds, tolerances }
    datasets.set(id, next)
    return next
  },
  sampleDataset: async (lang) => {
    const ds = sampleDataset(lang)
    datasets.set(ds.id, ds)
    return ds
  },
  getDataset: async (id) => {
    const ds = datasets.get(id)
    if (!ds) throw new ApiError(404, 'not_found', 'This dataset was not found.')
    return ds
  },
  createRun: async (body: CreateRunBody) => {
    const id = hex(12)
    runs.set(id, {
      id,
      lang: body.lang,
      filename: body.filename,
      source: body.source,
      created_at: new Date().toISOString(),
      mode: 'differs',
      reason: null
    })
    return { run_id: id }
  },
  streamRun: (id, onEvent) => stream(id, onEvent),
  cancelRun: async () => ({ ok: true }),
  getRun: async (id) => buildRun(recFor(id)),
  fixRun: async (id) => {
    const rec = recFor(id)
    await wait(1300 * scale())
    rec.mode = 'fixed'
    return buildRun(rec)
  },
  keepRun: async (id, reason) => {
    const text = reason.trim()
    if (text.length < 1 || text.length > 1000) throw new ApiError(422, 'invalid_request', 'Give a reason of 1 to 1000 characters.')
    const rec = recFor(id)
    rec.mode = 'kept'
    rec.reason = text
    return buildRun(rec)
  },
  undoRun: async (id) => {
    const rec = recFor(id)
    rec.mode = 'differs'
    rec.reason = null
    return buildRun(rec)
  },
  listRuns: async () => {
    const items = Array.from(runs.values())
      .reverse()
      .map(toItem)
    return { items, total: items.length }
  },
  deleteRun: async (id) => {
    runs.delete(id)
    return { ok: true }
  },
  pythonUrl: (id) => {
    const text = buildRun(recFor(id)).current.python + '\n'
    return 'data:text/x-python;charset=utf-8,' + encodeURIComponent(text)
  },
  exportReport: async (id) => exportFor(recFor(id)),
  exportUrl: (id, kind) => {
    if (kind === 'pdf') return 'data:application/pdf;base64,' + btoa('%PDF-1.4\n% mock report ' + id)
    const body = kind === 'json' ? JSON.stringify(exportFor(recFor(id)), null, 2) : '<!doctype html><title>Report</title><p>Report ' + id
    return `data:${kind === 'json' ? 'application/json' : 'text/html'};charset=utf-8,` + encodeURIComponent(body)
  },
  verifyReport: async (file) => {
    await wait(600 * scale())
    const ext = (file.name.split('.').pop() || '').toLowerCase()
    if (ext !== 'pdf' && ext !== 'json') throw new ApiError(422, 'invalid_request', 'This file is not a signed Parity report.')
    const out: VerifyResult = {
      status: 'valid',
      this_instance: true,
      signed_at: new Date().toISOString(),
      key_fingerprint: fakeHash('instance key').slice(0, 16),
      filename: canned.sas.file,
      matched: canned.sas.checks.length,
      total: canned.sas.checks.length,
      state: 'fixed',
      keep_reason: null,
      reason: null
    }
    return out
  }
}
