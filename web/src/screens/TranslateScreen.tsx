import { useEffect, useState } from 'react'
import { api, errorMessage } from '../api'
import type { Lang } from '../api/types'
import { Button } from '../components/Button'
import { CodeEditor } from '../components/CodeEditor'
import { detect, extOf, langFromExt, readText } from '../lib/files'
import { sv } from '../lib/format'
import { prefersReducedMotion } from '../lib/hooks'
import { nav } from '../state/router'
import { fileNameOf, useStore } from '../state/store'

function Hero() {
  return (
    <h1 className="hero">
      <span className="line">
        <span style={sv({ '--i': 0 })}>Move to Python.</span>
      </span>
      <span className="line dim">
        <span style={sv({ '--i': 1 })}>Prove it matches.</span>
      </span>
    </h1>
  )
}

const LABEL: Record<Lang, string> = { sas: 'SAS', vba: 'VBA' }

export function TranslateScreen() {
  const { state, dispatch, toast } = useStore()
  const { lang, source, health } = state
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const [shown, setShown] = useState<Lang>(lang)
  const [fade, setFade] = useState(false)

  useEffect(() => {
    if (lang === shown) return
    setFade(true)
    const t = window.setTimeout(
      () => {
        setShown(lang)
        setFade(false)
      },
      prefersReducedMotion() ? 0 : 140
    )
    return () => clearTimeout(t)
  }, [lang, shown])

  useEffect(() => {
    const over = (e: DragEvent) => {
      e.preventDefault()
      setDrag(true)
    }
    const leave = (e: DragEvent) => {
      if (!e.relatedTarget) setDrag(false)
    }
    const drop = async (e: DragEvent) => {
      e.preventDefault()
      setDrag(false)
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]
      if (!f) return
      const ext = extOf(f.name)
      if (ext === 'xlsx' || ext === 'xlsm') {
        toast('Save the macro as a .bas or .txt file.')
        return
      }
      try {
        const text = await readText(f)
        const next = langFromExt(ext) ?? detect(text) ?? 'sas'
        dispatch({ type: 'file', source: text, lang: next, filename: f.name })
      } catch {
        toast('That file could not be read.')
      }
    }
    window.addEventListener('dragover', over)
    window.addEventListener('dragleave', leave)
    window.addEventListener('drop', drop)
    return () => {
      window.removeEventListener('dragover', over)
      window.removeEventListener('dragleave', leave)
      window.removeEventListener('drop', drop)
    }
  }, [dispatch, toast])

  const translate = async () => {
    if (!source.trim()) {
      toast('Paste some code first.')
      return
    }
    if (busy) return
    setBusy(true)
    try {
      const ds = await api.sampleDataset(lang)
      dispatch({ type: 'dataset', dataset: ds })
      const { run_id } = await api.createRun({ lang, filename: fileNameOf(state), source, dataset_id: ds.id })
      nav('/running/' + run_id)
    } catch (e) {
      toast(errorMessage(e))
      setBusy(false)
    }
  }

  const configured = health ? health.translation_model.configured : false
  const runtime = health ? `Python ${health.python} · pandas ${health.pandas}` : 'Python 3.12 · pandas 2.2'

  return (
    <>
      <Hero />
      <p className="sub rise" style={sv({ '--i': 3 })}>
        Translate SAS and VBA, run both on your data, and see every number that differs.
      </p>
      <CodeEditor
        index={4}
        lang={lang}
        value={source}
        drag={drag}
        onChange={(v) => {
          const d = detect(v)
          dispatch({ type: 'source', source: v, lang: d && d !== lang ? d : undefined })
        }}
        onLang={(l) => dispatch({ type: 'lang', lang: l, sample: true })}
        onSubmit={translate}
        status={
          <>
            <i className="dot"></i>
            <span className="lang" style={{ opacity: fade ? 0 : 1 }}>
              {LABEL[shown]} detected
            </span>
            <span className="faint">{runtime}</span>
          </>
        }
        action={
          <Button variant="primary" onClick={translate} loading={busy}>
            Translate
          </Button>
        }
      />
      <p className="foot-hint rise" style={sv({ '--i': 5 })}>
        Drop .sas, .bas or .txt files anywhere on the page.
      </p>
      {!configured && (
        <p className="foot-hint rise" style={sv({ '--i': 5 })}>
          The translation model is not set. The rule layer translates common patterns.
        </p>
      )}
    </>
  )
}
