export type HlLang = 'sas' | 'vba' | 'py'

export interface Part {
  cls: 'k' | 's' | 'n' | 'c' | null
  text: string
}

const RX: Record<HlLang, RegExp> = {
  sas: /(\/\*.*?\*\/)|('[^']*'|"[^"]*")|(\b\d+(?:\.\d+)?\b)|\b(proc|means|data|set|run|quit|class|var|output|by|where|if|then|else|do|end|merge|keep|drop|format|input|sort|freq|tables|round|noprint|out|retain)\b/gi,
  vba: /('.*$)|("[^"]*")|(\b\d+(?:\.\d+)?\b)|\b(Sub|End|Dim|As|Long|Double|String|For|To|Next|If|Then|Else|ElseIf|Function|Set|Call|Cells|Range|Round|Exit|And|Or)\b/gi,
  py: /(#.*$)|('[^']*'|"[^"]*")|(\b\d+(?:\.\d+)?\b)|\b(import|from|as|def|return|for|in|if|else|elif|with|lambda)\b/g
}

export function tokenize(line: string, lang: HlLang): Part[] {
  const rx = RX[lang]
  rx.lastIndex = 0
  const out: Part[] = []
  let last = 0
  let m: RegExpExecArray | null
  while ((m = rx.exec(line))) {
    if (m[0].length === 0) {
      rx.lastIndex++
      continue
    }
    if (m.index > last) out.push({ cls: null, text: line.slice(last, m.index) })
    out.push({ cls: m[1] ? 'c' : m[2] ? 's' : m[3] ? 'n' : 'k', text: m[0] })
    last = m.index + m[0].length
  }
  if (last < line.length) out.push({ cls: null, text: line.slice(last) })
  return out
}
