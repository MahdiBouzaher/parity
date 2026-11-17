import { useState } from 'react'
import { api, errorMessage, type VerifyResult } from '../api'
import { Button } from '../components/Button'
import { Chip } from '../components/Chip'
import { DropZone } from '../components/DropZone'
import { ErrorPanel } from '../components/ErrorPanel'
import { sv } from '../lib/format'

const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''

export function VerifyScreen() {
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<VerifyResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const check = async (file: File) => {
    setBusy(true)
    setError(null)
    try {
      setResult(await api.verifyReport(file))
    } catch (e) {
      setResult(null)
      setError(errorMessage(e))
    }
    setBusy(false)
  }

  const again = () => {
    setResult(null)
    setError(null)
  }

  return (
    <>
      <h2 className="run-title rise" style={sv({ '--i': 0 })}>
        Verify a report
      </h2>
      <p className="run-sub rise" style={sv({ '--i': 1 })}>
        Check that a signed report has not changed since it was signed.
      </p>
      {error ? (
        <div style={{ marginTop: 24 }}>
          <ErrorPanel title="This file could not be verified" message={error} onBack={again} index={2} />
        </div>
      ) : result ? (
        <div className="panel vpanel rise" style={sv({ '--i': 2 })}>
          {result.status === 'valid' ? (
            <>
              <Chip variant="ok" text="Signature valid" />
              <p className="vline">
                {result.this_instance ? 'Signed by this Parity instance on ' : 'Signed by another Parity instance on '}
                {when(result.signed_at)}
              </p>
            </>
          ) : (
            <>
              <Chip variant="warn" text="Modified" />
              <p className="vline">This report changed after it was signed</p>
              {result.reason ? <p className="vsub">{result.reason}</p> : null}
            </>
          )}
          {result.filename ? <p className="vsub">{result.filename}</p> : null}
          {result.matched !== null && result.total !== null ? (
            <p className="vsub">{`${result.matched} of ${result.total} checks`}</p>
          ) : null}
          {result.keep_reason ? (
            <p className="kreason">
              Reason for accepted difference: <b>{result.keep_reason}</b>
            </p>
          ) : null}
          {result.key_fingerprint ? (
            <p className="vfp">
              <small>Key fingerprint</small>
              {result.key_fingerprint}
            </p>
          ) : null}
          <div className="acts">
            <Button onClick={again}>Verify another file</Button>
          </div>
        </div>
      ) : (
        <div className="panel vdrop rise" style={sv({ '--i': 2 })}>
          <DropZone
            label="Drop a signed PDF or JSON, or choose a file"
            hint="A report exported from Parity"
            accept=".pdf,.json"
            busy={busy}
            busyLabel="Checking"
            onFile={check}
          />
        </div>
      )}
    </>
  )
}
