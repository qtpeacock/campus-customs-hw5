import { AGENTS, AGENT_ORDER, DAN_GEAR, toolLabel } from '../agents'
import type { AgentEvent, AgentName } from '../types'
import { HandsomeDan } from './HandsomeDan'

type DanState = 'active' | 'waiting' | 'done' | 'benched' | 'off'

interface DanInfo {
  state: DanState
  line: string
  steps: number
}

/** Where each agent stands in the run being shown: working now, waiting on a teammate, done, or not needed. */
export function teamStates(events: AgentEvent[], live: boolean): Record<AgentName, DanInfo> {
  const runs = new Map<string, { agent: AgentName; ended: boolean; last: AgentEvent }>()
  for (const e of events) {
    const r = runs.get(e.run_id) ?? { agent: e.agent, ended: false, last: e }
    r.last = e
    if (e.event === 'run_end' || e.event === 'run_error') r.ended = true
    runs.set(e.run_id, r)
  }
  const latest = events[events.length - 1]
  const out = {} as Record<AgentName, DanInfo>
  for (const agent of AGENT_ORDER) {
    const mine = [...runs.entries()].filter(([, r]) => r.agent === agent)
    const steps = events.filter((e) => e.agent === agent && e.event === 'tool_call' && e.tool_name !== 'final_result').length
    const open = mine.find(([, r]) => !r.ended)
    if (live && open) {
      const [runId, r] = open
      if (latest && latest.run_id === runId) {
        const what = r.last.event === 'tool_call' ? (r.last.tool_name === 'ask_teammate' ? `Asking ${r.last.teammate}` : toolLabel(r.last.tool_name)) : 'Thinking…'
        out[agent] = { state: 'active', line: what, steps }
      } else {
        const child = [...runs.values()].find((c) => !c.ended && c.last.parent_run_id === runId)
        out[agent] = { state: 'waiting', line: child ? `Waiting on ${child.agent}` : 'Waiting…', steps }
      }
    } else if (mine.length > 0) {
      out[agent] = { state: 'done', line: live ? 'Reported back ✓' : `${steps} step${steps === 1 ? '' : 's'} ✓`, steps }
    } else {
      const line = live ? 'Standing by' : events.length ? 'Not needed' : 'Off duty'
      out[agent] = { state: live || events.length ? 'benched' : 'off', line, steps: 0 }
    }
  }
  return out
}

interface Props {
  events: AgentEvent[]
  live: boolean
  dancing: AgentName | null
  filter: AgentName | null
  onFilter: (a: AgentName | null) => void
}

export function TeamBar({ events, live, dancing, filter, onFilter }: Props) {
  const states = teamStates(events, live)
  return (
    <section className="team-strip" aria-label="The team">
      <div className="team-title">
        <span>The team</span>
        <small>{live ? 'on the clock' : filter ? `showing ${filter} only` : 'tap a Dan to follow them'}</small>
      </div>
      <div className="team-row">
        {AGENT_ORDER.map((agent) => {
          const info = states[agent]
          const isDancing = dancing === agent
          const mood = isDancing || info.state === 'done' ? 'happy' : info.state === 'off' || info.state === 'benched' ? 'asleep' : 'awake'
          return (
            <button
              key={agent}
              className={`dan-slot state-${info.state} ${isDancing ? 'dancing' : ''} ${filter === agent ? 'filtered' : ''}`}
              onClick={() => onFilter(filter === agent ? null : agent)}
              aria-pressed={filter === agent}
              title={`${agent}: ${AGENTS[agent].role}. Wears a ${DAN_GEAR[agent].gear}. Click to show only ${agent} in the feed.`}
            >
              {info.state === 'active' && <span className="dan-bubble">{info.line}</span>}
              <span className="dan-figure">
                <HandsomeDan agent={agent} mood={mood} size={64} />
                {(info.state === 'off' || info.state === 'benched') && <span className="zzz" aria-hidden="true">z<small>z</small></span>}
                {info.steps > 0 && <span className="step-count" title="Tools used this run">{info.steps}</span>}
              </span>
              <span className="dan-name">{agent}</span>
              <span className="dan-line">{isDancing ? 'Closed it out! 🎉' : info.state === 'active' ? 'Working' : info.line}</span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
