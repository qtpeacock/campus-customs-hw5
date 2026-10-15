import { money, shopDate } from '../agents'
import type { Cash } from '../types'
import { CashBar } from './CashBar'

interface Props {
  dateToday: string
  cash: Cash | null
  opening: number
  preview: number | null
  cashChange: { delta: number; label: string; key: number } | null
  backendUp: boolean | null
  model: string | null
  busy: boolean
  onReset: () => void
}

export function Header({ dateToday, cash, opening, preview, cashChange, backendUp, model, busy, onReset }: Props) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">CC</span>
        <div>
          <h1>Campus Customs Ops Desk</h1>
          <p className="brand-sub">
            {dateToday ? <>Shop date <strong>{shopDate(dateToday)}</strong></> : 'Loading…'}
            <span className={`dot ${backendUp ? 'up' : backendUp === false ? 'down' : ''}`} />
            {backendUp ? `Backend connected${model ? ` · ${model}` : ''}` : backendUp === false ? 'Backend offline' : 'Connecting…'}
          </p>
        </div>
      </div>

      <div className="scorecard" aria-live="polite">
        <div className="score-top">
          <span className="cash-label">Checking</span>
          <span className="cash-balance">{cash ? money(cash.balance) : '—'}</span>
          {cashChange && (
            <span key={cashChange.key} className={`cash-change ${cashChange.delta < 0 ? 'down' : 'up'}`}>
              {cashChange.delta < 0 ? '−' : '+'}
              {money(Math.abs(cashChange.delta))} · {cashChange.label}
            </span>
          )}
        </div>
        {cash && <CashBar cash={cash} opening={opening} preview={preview} />}
      </div>

      <button className="btn btn-light" onClick={onReset} disabled={busy} title="Copy the original database over the working copy">
        ↺ Reset board
      </button>
    </header>
  )
}
