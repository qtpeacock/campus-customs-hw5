import { useEffect, useRef, useState } from 'react'
import { answerOf, clock, stringArg, toolArgs, toolLabel } from '../agents'
import type { AgentEvent, AgentName } from '../types'
import { AgentBadge } from './AgentBadge'

// Tools that change the board (requests, drafts, notes, status) read as actions, not lookups.
const BOARD_ACTIONS = new Set([
  'request_payment', 'request_purchase_order', 'request_price_override',
  'draft_customer_message', 'add_ticket_note', 'set_ticket_status',
])

type View = 'all' | 'talk' | 'actions'
const VIEWS: { key: View; label: string; hint: string }[] = [
  { key: 'all', label: 'Everything', hint: 'Every step' },
  { key: 'talk', label: 'Conversation', hint: 'Who asked whom, and what they reported back' },
  { key: 'actions', label: 'Board actions', hint: 'Only steps that changed something on the board' },
]

function shown(e: AgentEvent, view: View): boolean {
  if (e.event === 'tool_call' && e.tool_name === 'final_result') return false
  if (e.event === 'model_response' && !e.text) return false
  if (e.event === 'tool_result') return false
  if (view === 'all') return true
  const isAsk = e.event === 'tool_call' && e.tool_name === 'ask_teammate'
  const isAction = e.event === 'tool_call' && BOARD_ACTIONS.has(e.tool_name ?? '')
  const isBookend = e.event === 'run_start' || e.event === 'run_end' || e.event === 'run_error'
  if (view === 'talk') return isAsk || isBookend || e.event === 'model_response' || e.event === 'delegation_refused'
  return isAction || (isBookend && e.depth === 0)
}

function Row({ e }: { e: AgentEvent }) {
  const indent = { marginLeft: `${e.depth * 26}px` }
  const head = (
    <>
      <span className="feed-time">{clock(e.timestamp)}</span>
      <AgentBadge agent={e.agent} size="sm" />
      <span className="feed-agent">{e.agent}</span>
    </>
  )

  switch (e.event) {
    case 'run_start':
      return (
        <li className={`feed-row start depth-${e.depth}`} style={indent}>
          {head}
          <span className="feed-verb">{e.depth === 0 ? 'picked up the ticket' : 'joined in'}</span>
        </li>
      )
    case 'tool_call': {
      if (e.tool_name === 'ask_teammate') {
        return (
          <li className="feed-row ask" style={indent}>
            {head}
            <span className="feed-verb">asks</span>
            {e.teammate && <AgentBadge agent={e.teammate} size="sm" />}
            <strong>{e.teammate}</strong>
            <p className="bubble ask-bubble">{stringArg(e.tool_args, 'task')}</p>
          </li>
        )
      }
      const action = BOARD_ACTIONS.has(e.tool_name ?? '')
      const args = toolArgs(e.tool_args)
      return (
        <li className={`feed-row tool ${action ? 'action' : ''}`} style={indent}>
          {head}
          <span className={`tool-label ${action ? 'action' : ''}`} title={e.tool_name ?? ''}>
            {action ? '★ ' : ''}
            {toolLabel(e.tool_name)}
          </span>
          {args && <code className="tool-args">{args}</code>}
        </li>
      )
    }
    case 'model_response':
      return (
        <li className="feed-row says" style={indent}>
          {head}
          <span className="feed-verb">says</span>
          <p className="bubble">{e.text}</p>
        </li>
      )
    case 'run_end':
      return (
        <li className={`feed-row done depth-${e.depth}`} style={indent}>
          {head}
          <span className="feed-verb">{e.depth === 0 ? 'made the call' : 'reported back'}</span>
          <p className="bubble done-bubble">{answerOf(e)}</p>
        </li>
      )
    case 'retry':
    case 'delegation_refused':
    case 'run_error':
      return (
        <li className="feed-row warn" style={indent}>
          {head}
          <span className="feed-verb">{e.event === 'run_error' ? 'failed' : 'hit a guardrail'}</span>
          <p className="bubble warn-bubble">{e.summary}</p>
        </li>
      )
    default:
      return null
  }
}

interface Props {
  events: AgentEvent[]
  live: boolean
  stale: boolean
  startedAt: string | null
  agentFilter: AgentName | null
  onClearFilter: () => void
}

export function AgentFeed({ events, live, stale, startedAt, agentFilter, onClearFilter }: Props) {
  const [view, setView] = useState<View>('all')
  const visible = events.filter((e) => shown(e, view) && (!agentFilter || e.agent === agentFilter))

  // Keep the newest event in view while a run is live, scrolling only the feed (not the page).
  const list = useRef<HTMLOListElement>(null)
  useEffect(() => {
    if (live && list.current) list.current.scrollTo({ top: list.current.scrollHeight, behavior: 'smooth' })
  }, [visible.length, live])

  return (
    <section className="panel tile feed" aria-label="Agent activity">
      <div className="panel-head">
        <h3>{live ? 'Live: agents at work' : 'Agent activity'}</h3>
        {live && <span className="live-dot">live</span>}
        {!live && startedAt && <span className="muted">Last run {new Date(startedAt).toLocaleString()}</span>}
      </div>
      <div className="feed-tools" role="group" aria-label="Show">
        {VIEWS.map((v) => (
          <button key={v.key} className={`chip-btn ${view === v.key ? 'on' : ''}`} onClick={() => setView(v.key)} title={v.hint} aria-pressed={view === v.key}>
            {v.label}
          </button>
        ))}
        {agentFilter && (
          <button className="chip-btn on filter" onClick={onClearFilter} title="Show every agent again">
            Only {agentFilter} ✕
          </button>
        )}
      </div>
      {stale && <p className="notice">This run happened before the last board reset, so its approvals and drafts were wiped.</p>}
      {events.length === 0 ? (
        <p className="empty">No agents have worked this ticket yet. Press <strong>▶ Run agent team</strong> to start.</p>
      ) : visible.length === 0 ? (
        <p className="empty">Nothing matches this view yet.</p>
      ) : (
        <ol className="feed-list" ref={list}>
          {visible.map((e) => (
            <Row key={e.index} e={e} />
          ))}
        </ol>
      )}
    </section>
  )
}
