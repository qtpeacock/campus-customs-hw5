import { useState } from 'react'
import { APPROVAL_LABEL, money } from '../agents'
import type { Approval } from '../types'
import { AgentBadge } from './AgentBadge'

interface Props {
  approvals: Approval[]
  approver: string
  onApproverChange: (name: string) => void
  onApprove: (a: Approval) => Promise<void>
  onReject: (a: Approval, note: string) => Promise<void>
  onPreview: (amount: number | null) => void // shows where the balance would land on the cash bar
}

function what(a: Approval): string {
  if (a.kind === 'invoice_payment') return `Invoice ${a.ref_id}`
  if (a.kind === 'rent_payment') return `Lease ${a.ref_id}`
  if (a.kind === 'purchase_order') return `${a.qty} × ${a.sku} size ${a.size} @ ${money(a.unit_price ?? 0)}`
  return `${a.qty} × ${a.sku} size ${a.size} at ${money(a.unit_price ?? 0)} each`
}

export function Approvals({ approvals, approver, onApproverChange, onApprove, onReject, onPreview }: Props) {
  const [busyId, setBusyId] = useState<number | null>(null)
  const [rejecting, setRejecting] = useState<number | null>(null)
  const [note, setNote] = useState('')
  const pending = approvals.filter((a) => a.status === 'pending')
  const decided = approvals.filter((a) => a.status !== 'pending')
  if (approvals.length === 0) return null

  const act = async (a: Approval, fn: () => Promise<void>) => {
    setBusyId(a.id)
    try {
      await fn()
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className={`approvals tile ${pending.length ? 'has-pending' : ''}`} aria-label="Approvals">
      <div className="approvals-head">
        <h3>{pending.length ? `🙋 Your call: ${pending.length} waiting` : 'Approvals'}</h3>
        {pending.length > 0 && (
          <label className="approver">
            Approving as
            <input
              value={approver}
              onChange={(e) => onApproverChange(e.target.value)}
              placeholder="Your name"
              aria-label="Your name"
            />
          </label>
        )}
      </div>
      {pending.length > 0 && (
        <p className="approvals-hint">Agents only prepare these. Nothing is paid or ordered until a person approves it here. Hover <strong>Approve &amp; pay</strong> to see where your balance lands.</p>
      )}

      <ul className="approval-list">
        {pending.map((a) => (
          <li key={a.id} className="approval pending card-3d">
            <div className="approval-main">
              <div className="approval-kind">
                <span className="approval-id">#{a.id}</span> {APPROVAL_LABEL[a.kind]}
                {!a.cash_out && <span className="tag">no cash moves</span>}
              </div>
              <div className="approval-what">{what(a)}</div>
              <div className="approval-reason">
                <AgentBadge agent={a.requested_by} size="sm" /> {a.reason}
              </div>
            </div>
            <div className="approval-amount">{money(a.amount)}</div>
            <div className="approval-actions">
              {rejecting === a.id ? (
                <form
                  className="reject-form"
                  onSubmit={(e) => {
                    e.preventDefault()
                    void act(a, () => onReject(a, note)).then(() => {
                      setRejecting(null)
                      setNote('')
                    })
                  }}
                >
                  <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why not?" autoFocus aria-label="Reason for rejecting" />
                  <button className="btn btn-small" disabled={!note.trim() || !approver.trim() || busyId === a.id}>
                    Reject
                  </button>
                  <button type="button" className="btn btn-small btn-ghost-dark" onClick={() => setRejecting(null)}>
                    Cancel
                  </button>
                </form>
              ) : (
                <>
                  <button
                    className="btn btn-primary btn-small"
                    disabled={!approver.trim() || busyId === a.id}
                    title={!approver.trim() ? 'Type your name first' : undefined}
                    onMouseEnter={() => a.cash_out && onPreview(a.amount)}
                    onMouseLeave={() => onPreview(null)}
                    onFocus={() => a.cash_out && onPreview(a.amount)}
                    onBlur={() => onPreview(null)}
                    onClick={() => {
                      onPreview(null)
                      void act(a, () => onApprove(a))
                    }}
                  >
                    {busyId === a.id ? 'Approving…' : a.cash_out ? `Approve & pay` : 'Approve'}
                  </button>
                  <button className="btn btn-small btn-ghost-dark" disabled={busyId === a.id} onClick={() => setRejecting(a.id)}>
                    Reject
                  </button>
                </>
              )}
            </div>
          </li>
        ))}
        {decided.map((a) => (
          <li key={a.id} className={`approval decided status-${a.status}`}>
            <div className="approval-main">
              <div className="approval-kind">
                <span className="approval-id">#{a.id}</span> {APPROVAL_LABEL[a.kind]} · {what(a)}
              </div>
            </div>
            <div className="approval-amount">{money(a.amount)}</div>
            <div className="approval-decided">{a.status}</div>
          </li>
        ))}
      </ul>
    </section>
  )
}
