import { when } from '../agents'
import type { BossDecision, Draft, TicketUpdate } from '../types'
import { HandsomeDan } from './HandsomeDan'

export function BossCall({ decision, answer }: { decision: BossDecision | null; answer: string | null }) {
  if (!decision && !answer) return null
  return (
    <section className="panel tile boss-call" aria-label="Boss's call">
      <div className="panel-head">
        <HandsomeDan agent="Boss" mood="happy" size={44} />
        <h3>Boss's call</h3>
        <span className="muted">when the run ended</span>
      </div>
      <p className="boss-decision">{decision?.decision ?? answer}</p>
      {decision && decision.needs_human.length > 0 && (
        <>
          <h4>Needs a person</h4>
          <ul className="tight">
            {decision.needs_human.map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        </>
      )}
      {decision && decision.next_steps.length > 0 && (
        <>
          <h4>Next</h4>
          <ul className="tight">
            {decision.next_steps.map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        </>
      )}
    </section>
  )
}

export function Drafts({ drafts }: { drafts: Draft[] }) {
  if (drafts.length === 0) return null
  return (
    <section className="panel tile drafts" aria-label="Draft messages">
      <div className="panel-head">
        <h3>✉️ Draft messages</h3>
        <span className="tag">not sent</span>
      </div>
      {drafts.map((d) => (
        <article key={d.id} className="draft">
          <div className="draft-meta">
            <strong>To {d.recipient}</strong> · “{d.subject}” · by {d.written_by}
          </div>
          <p className="draft-body">{d.body}</p>
        </article>
      ))}
    </section>
  )
}

export function BoardNotes({ updates }: { updates: TicketUpdate[] }) {
  if (updates.length === 0) return null
  return (
    <details className="panel tile notes">
      <summary>
        <h3>On the board ({updates.length} notes)</h3>
      </summary>
      <ol className="notes-list">
        {updates.map((u, i) => (
          <li key={i} className={u.agent.endsWith('(human)') ? 'by-human' : ''}>
            <span className="note-who">{u.agent}</span>
            <span className="note-when">{when(u.created_at)}</span>
            {u.status_before !== u.status_after && (
              <span className="note-status">
                {u.status_before} → {u.status_after}
              </span>
            )}
            <p>{u.note}</p>
          </li>
        ))}
      </ol>
    </details>
  )
}
