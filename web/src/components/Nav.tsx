import { nav } from '../state/router'

export function Nav() {
  return (
    <header className="nav">
      <button className="brand" onClick={() => nav('/')} aria-label="Parity, back to start">
        <span className="mark" aria-hidden="true">
          <i></i>
          <i></i>
        </span>
        Parity
      </button>
      <div className="navlinks">
        <button className="link" onClick={() => nav('/history')}>
          History
        </button>
      </div>
    </header>
  )
}
