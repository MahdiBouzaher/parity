import type { CheckKind, Lang } from './types'

export interface CannedCheck {
  label: string
  kind: CheckKind
  expected: string
  actual: string
  delta: string | null
  details: string | null
}

export interface CannedLang {
  label: 'SAS' | 'VBA'
  file: string
  stmts: number
  table: string
  src: string[]
  srcFlag: number
  pyBefore: string[]
  pyAfter: string[]
  flagBefore: number
  flagAfter: number
  changed: number[]
  tag: string
  reason: string
  rowsLabel: string
  checks: CannedCheck[]
  diffIndex: number
  whyTitle: string
  whyBody: string[]
  whyNote: string
  fixedBody: string
}

const ok = (label: string, kind: CheckKind, value: string): CannedCheck => ({
  label,
  kind,
  expected: value,
  actual: value,
  delta: null,
  details: null
})

const EXTRA: CannedCheck[] = [
  ok('Sum of balance', 'stat', '962,114,880.37'),
  ok('Mean of exposure', 'stat', '26,644.97'),
  ok('Mean of lgd', 'stat', '0.4398'),
  ok('Max of exposure', 'stat', '2,500,000.00'),
  ok('Min of exposure', 'stat', '1,000.00'),
  ok('Std dev of balance', 'stat', '18,204.55'),
  ok('Distinct segments', 'stat', '6'),
  ok('Null count in pd', 'stat', '0'),
  ok('Row order', 'cells', 'unchanged')
]

const sasDiff: CannedCheck = {
  label: 'Sum of provisions',
  kind: 'stat',
  expected: '41,902,118.55',
  actual: '41,902,121.17',
  delta: '+2.62',
  details: '312 of 48,210 rates sit exactly on a tie at the 4th decimal.'
}

const vbaDiff: CannedCheck = {
  label: 'Mean of provisions',
  kind: 'stat',
  expected: '869.16',
  actual: '873.03',
  delta: '+3.87',
  details: '214 of 48,210 rows have a blank exposure.'
}

export const canned: Record<Lang, CannedLang> = {
  sas: {
    label: 'SAS',
    file: 'loss_provision.sas',
    stmts: 8,
    table: 'provisions',
    src: [
      'data provisions;',
      '  set loans;',
      '  rate = round(pd * lgd, 0.0001);',
      '  prov = exposure * rate;',
      'run;',
      '',
      'proc means data=provisions sum;',
      '  var prov;',
      'run;'
    ],
    srcFlag: 3,
    pyBefore: [
      'import pandas as pd',
      '',
      'loans = pd.read_csv("input.csv")',
      '',
      'provisions = loans.copy()',
      'provisions["rate"] = (',
      '    provisions["pd"] * provisions["lgd"]',
      ').round(4)',
      'provisions["prov"] = (',
      '    provisions["exposure"] * provisions["rate"]',
      ')',
      '',
      'total = provisions["prov"].sum()'
    ],
    pyAfter: [
      'import numpy as np',
      'import pandas as pd',
      '',
      'def round_half_up(s, n):',
      '    q = 10 ** n',
      '    return np.sign(s) * np.floor(np.abs(s) * q + 0.5 + 1e-9) / q',
      '',
      'loans = pd.read_csv("input.csv")',
      '',
      'provisions = loans.copy()',
      'provisions["rate"] = (',
      '    provisions["pd"] * provisions["lgd"]',
      ').pipe(round_half_up, 4)',
      'provisions["prov"] = (',
      '    provisions["exposure"] * provisions["rate"]',
      ')',
      '',
      'total = provisions["prov"].sum()'
    ],
    flagBefore: 8,
    flagAfter: 13,
    changed: [1, 4, 5, 6, 13],
    tag: 'rounding',
    reason: 'SAS and pandas round a tie differently.',
    rowsLabel: 'Row count after filter',
    checks: [
      ok('Row count after filter', 'rows', '48,210'),
      ok('Sum of exposure', 'stat', '1,284,553,901.20'),
      ok('Mean of pd', 'stat', '0.0342'),
      sasDiff,
      ...EXTRA
    ],
    diffIndex: 3,
    whyTitle: 'Why the sum of provisions differs',
    whyBody: [
      'SAS rounds a tie away from zero. pandas rounds a tie to the nearest even digit.',
      '312 of 48,210 rates sit exactly on a tie at the 4th decimal.'
    ],
    whyNote: 'Applying the fix switches the translation to round half up and runs it again.',
    fixedBody: 'All 13 checks match. The translation now uses a round half up helper, the same rule SAS applies.'
  },
  vba: {
    label: 'VBA',
    file: 'loss_provision.bas',
    stmts: 9,
    table: 'result',
    src: [
      'Sub Provisions()',
      '  Dim i As Long, total As Double',
      '  For i = 2 To lastRow',
      '    rate = Cells(i, 2) * Cells(i, 3)',
      '    Cells(i, 5) = Cells(i, 4) * rate',
      '    total = total + Cells(i, 5)',
      '  Next i',
      '  Cells(1, 7) = total / (lastRow - 1)',
      'End Sub'
    ],
    srcFlag: 5,
    pyBefore: [
      'import pandas as pd',
      '',
      'df = pd.read_csv("input.csv")',
      'df["rate"] = df["pd"] * df["lgd"]',
      'df["prov"] = df["exposure"] * df["rate"]',
      'total = df["prov"].sum()',
      'avg = df["prov"].mean()',
      'result = df'
    ],
    pyAfter: [
      'import pandas as pd',
      '',
      'df = pd.read_csv("input.csv")',
      'df["rate"] = df["pd"] * df["lgd"]',
      'df["prov"] = df["exposure"].fillna(0) * df["rate"]',
      'total = df["prov"].sum()',
      'avg = df["prov"].mean()',
      'result = df'
    ],
    flagBefore: 5,
    flagAfter: 5,
    changed: [5],
    tag: 'missing values',
    reason: 'VBA counts a blank cell as zero. pandas skips it.',
    rowsLabel: 'Row count after filter',
    checks: [
      ok('Row count after filter', 'rows', '48,210'),
      ok('Sum of exposure', 'stat', '1,284,553,901.20'),
      ok('Sum of provisions', 'stat', '41,902,118.55'),
      vbaDiff,
      ...EXTRA
    ],
    diffIndex: 3,
    whyTitle: 'Why the mean of provisions differs',
    whyBody: ['VBA counts a blank cell as zero. pandas skips it.', '214 of 48,210 rows have a blank exposure.'],
    whyNote: 'Applying the fix fills blank cells with 0 before the arithmetic and runs it again.',
    fixedBody: 'All 13 checks match. The translation now treats blank cells as zero, the same rule VBA applies.'
  }
}

export const SAMPLES: Record<Lang, string> = {
  sas: canned.sas.src.join('\n'),
  vba: canned.vba.src.join('\n')
}

export const PREVIEW_INPUT: (string | null)[][] = [
  ['1001', 'retail', '25000.00', '18211.40', '0.0125', '0.50'],
  ['1002', 'sme', '184500.00', '120340.55', '0.0375', '0.50'],
  ['1003', 'corporate', '1250000.00', '980000.00', '0.0150', '0.25'],
  ['1004', 'mortgage', '310000.00', '254100.10', '0.0220', '0.45'],
  ['1005', 'cards', null, '2100.00', '0.0910', '0.75'],
  ['1006', 'leasing', '76400.00', '51200.00', '0.0010', '0.75'],
  ['1007', 'retail', '18900.00', '9980.30', '0.1340', '0.40'],
  ['1008', 'sme', '92000.00', '61800.00', '0.0480', '0.45']
]

export const ROWS_TOTAL = 48210
export const RUN_SECONDS = 3.2
