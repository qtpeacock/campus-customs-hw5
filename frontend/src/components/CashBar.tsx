import { money } from '../agents'
import type { Cash } from '../types'

interface Props {
  cash: Cash
  opening: number // the balance at the last reset: what's left plus everything paid since
  preview: number | null // amount of the approval being hovered, if any
}

/**
 * The balance as a bar that shrinks as money goes out:
 * solid blue = available, striped = held for approvals, empty = already spent.
 * Hovering an "Approve & pay" button drops a marker where the balance will land.
 */
export function CashBar({ cash, opening, preview }: Props) {
  const total = Math.max(opening, cash.balance, 1)
  const pct = (n: number) => `${Math.max(0, Math.min(100, (n / total) * 100))}%`
  const spent = Math.max(0, opening - cash.balance)
  const after = preview !== null ? cash.balance - preview : null

  return (
    <div className="cash-bar-wrap">
      <div
        className="cash-bar"
        role="img"
        aria-label={`${money(cash.available)} available, ${money(cash.already_committed)} held for approvals, ${money(spent)} spent of ${money(opening)}`}
      >
        <div className="cash-seg available" style={{ width: pct(cash.available) }} />
        <div className="cash-seg held" style={{ width: pct(cash.already_committed) }} />
        {after !== null && <div className="cash-marker" style={{ left: pct(after) }} />}
      </div>
      <div className="cash-legend">
        <span><i className="key available" /> {money(cash.available)} free</span>
        {cash.already_committed > 0 && <span><i className="key held" /> {money(cash.already_committed)} held</span>}
        {spent > 0 && <span><i className="key spent" /> {money(spent)} spent</span>}
        {after !== null ? (
          <span className="of after">after this payment: {money(after)}</span>
        ) : (
          <span className="of">of {money(opening)}</span>
        )}
      </div>
    </div>
  )
}
