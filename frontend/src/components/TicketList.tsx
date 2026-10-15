import { STATUS_LABEL, TICKET_TYPE } from '../agents'
import type { Ticket, TicketStatus } from '../types'

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  runningId: number | null
  onSelect: (id: number) => void
}

const TRACK = ['Open', 'Agents', 'Your call', 'Done'] as const
const STEP: Record<TicketStatus, number> = { open: 0, in_progress: 1, waiting_approval: 2, resolved: 3 }

/** A little board-game track: where this ticket is on its way to done. */
export function Track({ status, running }: { status: TicketStatus; running: boolean }) {
  const at = running ? 1 : STEP[status]
  return (
    <ol className="track" aria-label={`Progress: ${TRACK[at]}`}>
      {TRACK.map((label, i) => (
        <li key={label} className={i < at ? 'passed' : i === at ? 'here' : ''}>
          <span className="track-dot" />
          <span className="track-label">{label}</span>
        </li>
      ))}
    </ol>
  )
}

export function TicketList({ tickets, selectedId, runningId, onSelect }: Props) {
  return (
    <nav className="ticket-list" aria-label="Tickets">
      <h2 className="section-title">Tickets</h2>
      {tickets.map((t) => {
        const pending = t.approvals.filter((a) => a.status === 'pending').length
        const running = runningId === t.id
        const statusKey = running ? 'running' : t.status
        const type = TICKET_TYPE[t.type] ?? { label: t.type, icon: '📋' }
        return (
          <button
            key={t.id}
            className={`ticket-card tile type-${t.type} ${selectedId === t.id ? 'selected' : ''} status-${statusKey}`}
            onClick={() => onSelect(t.id)}
            aria-current={selectedId === t.id}
          >
            <div className="card-band">
              <span className="type-icon" aria-hidden="true">{type.icon}</span>
              <span>{type.label}</span>
              <span className="ticket-id">#{t.id}</span>
            </div>
            <div className="card-body">
              <div className="ticket-subject">{t.subject}</div>
              <div className="ticket-meta">{t.requester}</div>
              <span className={`status-pill pill-${statusKey}`}>
                {running ? 'Agents working…' : STATUS_LABEL[t.status]}
                {!running && pending > 0 && ` · ${pending}`}
              </span>
              <Track status={t.status} running={running} />
            </div>
          </button>
        )
      })}
    </nav>
  )
}
