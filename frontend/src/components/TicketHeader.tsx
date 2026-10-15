import { STATUS_LABEL, TICKET_TYPE } from '../agents'
import type { Ticket } from '../types'
import { Track } from './TicketList'

interface Props {
  ticket: Ticket
  running: boolean
  otherRunning: boolean
  onRun: () => void
}

export function TicketHeader({ ticket, running, otherRunning, onRun }: Props) {
  const resolved = ticket.state === 'resolved'
  const type = TICKET_TYPE[ticket.type] ?? { label: ticket.type, icon: '📋' }
  const asks = [
    ticket.qty && ticket.sku ? `${ticket.qty} × ${ticket.sku}${ticket.size ? ` · size ${ticket.size}` : ''}` : null,
    ticket.invoice_id ? `invoice ${ticket.invoice_id}` : null,
    ticket.lease_id ? `lease ${ticket.lease_id}` : null,
  ].filter(Boolean)

  // While requests wait on a person, the team waits too: re-running then would race the decision.
  const awaitingYou = ticket.approvals.some((a) => a.status === 'pending')
  let label = '▶ Run agent team'
  if (running) label = 'Agents working…'
  else if (resolved) label = '✓ Resolved'
  else if (awaitingYou) label = 'Waiting on your call'
  else if (ticket.status !== 'open') label = '↻ Run team again'

  return (
    <section className={`ticket-header tile ${resolved ? 'is-resolved' : ''}`}>
      <span className="big-icon" aria-hidden="true">{type.icon}</span>
      <div className="ticket-header-text">
        <p className="eyebrow">
          {type.label} · Ticket #{ticket.id} · {ticket.requester}
        </p>
        <h2>{ticket.subject}</h2>
        <p className="ticket-notes">“{ticket.notes}”</p>
        {asks.length > 0 && <p className="ticket-links">{asks.join(' · ')}</p>}
        <Track status={ticket.status} running={running} />
      </div>
      <div className="ticket-header-actions">
        <span className={`status-pill big pill-${running ? 'running' : ticket.status}`}>
          {running ? 'Agents working…' : STATUS_LABEL[ticket.status]}
        </span>
        <button
          className="btn btn-primary btn-big"
          onClick={onRun}
          disabled={running || resolved || otherRunning || awaitingYou}
          title={
            otherRunning
              ? 'Another ticket is running. One run at a time.'
              : awaitingYou
                ? 'Approve or reject the waiting requests first.'
                : undefined
          }
        >
          {running && <span className="spinner" aria-hidden="true" />}
          {label}
        </button>
      </div>
    </section>
  )
}
