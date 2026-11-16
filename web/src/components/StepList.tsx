import { CountText } from './CountText'

export interface StepView {
  label: string
  state: '' | 'active' | 'done'
  detail: string
}

function StepIcon() {
  return (
    <span className="ico">
      <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">
        <circle className="ring" cx="10" cy="10" r="9" />
        <path className="arc" d="M10 1 A9 9 0 0 1 19 10" strokeWidth="1.8" strokeLinecap="round" />
        <path className="tick" d="M6 10.4l2.8 2.8L14 7.4" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  )
}

function Detail({ text }: { text: string }) {
  const m = /^([\d,]+) (rows|checks)$/.exec(text)
  if (!m) return <>{text}</>
  return <CountText to={Number(m[1].replace(/,/g, ''))} suffix={' ' + m[2]} dur={m[2] === 'rows' ? 1500 : 900} />
}

export function StepList({ steps }: { steps: StepView[] }) {
  return (
    <ol className="steps">
      {steps.map((s, i) => (
        <li key={i} className={'step' + (s.state ? ' ' + s.state : '')}>
          <StepIcon />
          <span className="lbl">{s.label}</span>
          <span className="det">{s.detail ? <Detail text={s.detail} /> : null}</span>
        </li>
      ))}
    </ol>
  )
}
