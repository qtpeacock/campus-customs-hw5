import { AGENTS, AGENT_ORDER, answerOf } from '../agents'
import type { AgentEvent, AgentName } from '../types'
import { HandsomeDan } from './HandsomeDan'

interface AgentWork {
  agent: AgentName
  askedBy: AgentName | null
  tools: string[]
  asked: AgentName[]
  answer: string | null
  state: 'working' | 'done' | 'failed'
}

/** One entry per agent run in this ticket run, built from its events. */
function summarize(events: AgentEvent[]): AgentWork[] {
  const runs = new Map<string, AgentWork>()
  const agentOfRun = new Map<string, AgentName>()
  for (const e of events) {
    agentOfRun.set(e.run_id, e.agent)
    if (!runs.has(e.run_id)) {
      runs.set(e.run_id, { agent: e.agent, askedBy: null, tools: [], asked: [], answer: null, state: 'working' })
    }
    const w = runs.get(e.run_id)!
    if (e.event === 'run_start' && e.parent_run_id) w.askedBy = agentOfRun.get(e.parent_run_id) ?? null
    if (e.event === 'tool_call' && e.tool_name === 'ask_teammate' && e.teammate && !w.asked.includes(e.teammate)) w.asked.push(e.teammate)
    if (e.event === 'tool_call' && e.tool_name && !['ask_teammate', 'final_result'].includes(e.tool_name) && !w.tools.includes(e.tool_name)) w.tools.push(e.tool_name)
    if (e.event === 'run_end') {
      w.state = 'done'
      w.answer = answerOf(e)
    }
    if (e.event === 'run_error') {
      w.state = 'failed'
      w.answer = e.text
    }
  }
  return [...runs.values()].sort((a, b) => AGENT_ORDER.indexOf(a.agent) - AGENT_ORDER.indexOf(b.agent))
}

export function AgentSummary({ events, live }: { events: AgentEvent[]; live: boolean }) {
  const work = summarize(events)
  const idle = AGENT_ORDER.filter((a) => !work.some((w) => w.agent === a))

  return (
    <section className="panel tile summary" aria-label="What each agent did">
      <div className="panel-head">
        <h3>What each agent did</h3>
      </div>
      {work.length === 0 && <p className="empty">Nothing yet.</p>}
      <ul className="summary-list">
        {work.map((w, i) => (
          <li key={i} className={`summary-card card-3d ${AGENTS[w.agent].cls}-card state-${w.state}`}>
            <div className="summary-head">
              <HandsomeDan agent={w.agent} mood={w.state === 'done' ? 'happy' : 'awake'} size={44} />
              <div>
                <div className="summary-name">{w.agent}</div>
                <div className="summary-role">
                  {w.askedBy ? `asked by ${w.askedBy}` : 'top of the chain'}
                  {w.state === 'working' && ' · working…'}
                </div>
              </div>
            </div>
            {w.answer && <p className="summary-answer">{w.answer}</p>}
            {(w.tools.length > 0 || w.asked.length > 0) && (
              <div className="chips">
                {w.asked.map((a) => (
                  <span key={a} className="chip chip-ask">→ {a}</span>
                ))}
                {w.tools.map((t) => (
                  <span key={t} className="chip">{t}</span>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
      {!live && work.length > 0 && idle.length > 0 && (
        <p className="muted small">Not called on this ticket: {idle.join(', ')}</p>
      )}
    </section>
  )
}
