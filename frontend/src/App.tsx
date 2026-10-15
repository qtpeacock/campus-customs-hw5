import { useCallback, useEffect, useRef, useState } from 'react'
import { APPROVAL_LABEL, money } from './agents'
import { api } from './api'
import { AgentFeed } from './components/AgentFeed'
import { AgentSummary } from './components/AgentSummary'
import { Approvals } from './components/Approvals'
import { Header } from './components/Header'
import { Confetti } from './components/Confetti'
import { HandsomeDan } from './components/HandsomeDan'
import { BoardNotes, BossCall, Drafts } from './components/SidePanels'
import { TeamBar } from './components/TeamBar'
import { TicketHeader } from './components/TicketHeader'
import { TicketList } from './components/TicketList'
import type { AgentEvent, AgentName, Approval, Cash, RunInfo, Ticket } from './types'

const POLL_MS = 1500 // how often the live feed asks for new agent events
const IDLE_REFRESH_MS = 10000 // how often tickets and cash refresh when nothing is running
const DANCE_MS = 3600 // how long the closing Dan dances and the banner stays up

type Toast = { kind: 'ok' | 'error'; text: string }

/** The newest run among a ticket's events (events come oldest first). */
function latestRun(events: AgentEvent[]): AgentEvent[] {
  if (events.length === 0) return []
  const root = events[events.length - 1].root_run_id
  return events.filter((e) => e.root_run_id === root)
}

function merge(prev: AgentEvent[], next: AgentEvent[], root: string): AgentEvent[] {
  const byIndex = new Map(prev.filter((e) => e.root_run_id === root).map((e) => [e.index, e]))
  next.forEach((e) => byIndex.set(e.index, e))
  return [...byIndex.values()].sort((a, b) => a.index - b.index)
}

const message = (err: unknown) => (err instanceof Error ? err.message : String(err))

/** Who gets the credit when a ticket resolves: whoever asked for the last request a person
 *  decided (that decision is what closed it), or Boss if Boss closed it directly. */
function closer(t: Ticket): AgentName {
  const decided = t.approvals.filter((a) => a.status !== 'pending').sort((a, b) => b.id - a.id)
  return decided[0]?.requested_by ?? 'Boss'
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [dateToday, setDateToday] = useState('')
  const [cash, setCash] = useState<Cash | null>(null)
  const [cashChange, setCashChange] = useState<{ delta: number; label: string; key: number } | null>(null)
  const [backendUp, setBackendUp] = useState<boolean | null>(null)
  const [model, setModel] = useState<string | null>(null)
  const [lastReset, setLastReset] = useState<string | null>(null)
  // The selected ticket lives in the URL (#ticket-103), so a ticket can be linked or bookmarked.
  const [selectedId, setSelectedId] = useState<number | null>(() => {
    const m = window.location.hash.match(/ticket-(\d+)/)
    return m ? Number(m[1]) : null
  })
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [active, setActive] = useState<{ rootRunId: string; ticketId: number } | null>(null)
  const [runs, setRuns] = useState<Record<string, RunInfo>>({})
  const [toast, setToast] = useState<Toast | null>(null)
  const [approver, setApprover] = useState(() => localStorage.getItem('desk.approver') ?? '')
  const [agentFilter, setAgentFilter] = useState<AgentName | null>(null)
  const [preview, setPreview] = useState<number | null>(null)
  const [party, setParty] = useState<{ ticketId: number; agent: AgentName; key: number } | null>(null)

  const since = useRef(0)
  const prevBalance = useRef<number | null>(null)
  const prevStatus = useRef<Map<number, string>>(new Map())
  const selectedRef = useRef<number | null>(null)
  selectedRef.current = selectedId

  useEffect(() => localStorage.setItem('desk.approver', approver), [approver])
  useEffect(() => {
    setAgentFilter(null)
    if (selectedId !== null) window.history.replaceState(null, '', `#ticket-${selectedId}`)
  }, [selectedId])
  useEffect(() => {
    if (!cashChange) return
    const t = setTimeout(() => setCashChange(null), 9000) // the "−$X" chip is news, not a fixture
    return () => clearTimeout(t)
  }, [cashChange])
  useEffect(() => {
    if (!party) return
    const t = setTimeout(() => setParty(null), DANCE_MS)
    return () => clearTimeout(t)
  }, [party])
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 7000)
    return () => clearTimeout(t)
  }, [toast])

  const refreshBoard = useCallback(async (cashLabel?: string) => {
    try {
      const [t, c] = await Promise.all([api.tickets(), api.cash()])
      // A ticket that just turned resolved gets confetti, and the Dan who closed it dances.
      const justResolved = t.tickets.find((x) => x.status === 'resolved' && prevStatus.current.has(x.id) && prevStatus.current.get(x.id) !== 'resolved')
      if (justResolved) setParty({ ticketId: justResolved.id, agent: closer(justResolved), key: Date.now() })
      prevStatus.current = new Map(t.tickets.map((x) => [x.id, x.status]))
      setTickets(t.tickets)
      setDateToday(t.date_today)
      if (prevBalance.current !== null && c.balance !== prevBalance.current) {
        setCashChange({ delta: c.balance - prevBalance.current, label: cashLabel ?? 'balance changed', key: Date.now() })
      }
      prevBalance.current = c.balance
      setCash(c)
      setBackendUp(true)
      setSelectedId((id) => id ?? t.tickets.find((x) => x.state === 'open')?.id ?? t.tickets[0]?.id ?? null)
    } catch (err) {
      setBackendUp(false)
      setToast({ kind: 'error', text: message(err) })
    }
  }, [])

  // Boss's full decision lives in the backend's run list, which only covers runs since it
  // last started. Older runs still show in the feed (from the audit trail), just without it.
  const rememberRun = useCallback((root: string) => {
    api
      .runs()
      .then(({ runs: list }) => {
        const info = list.find((r) => r.root_run_id === root)
        if (info) setRuns((r) => ({ ...r, [root]: info }))
      })
      .catch(() => {})
  }, [])

  // First load: is the backend up, is a run already going, when was the last reset?
  useEffect(() => {
    api
      .health()
      .then(async (h) => {
        setModel(h.model)
        setLastReset(h.last_reset_at)
        if (h.run_in_progress) {
          const info = await api.run(h.run_in_progress)
          setSelectedId(info.ticket_id)
          setActive({ rootRunId: info.root_run_id, ticketId: info.ticket_id })
        }
      })
      .catch(() => setBackendUp(false))
    void refreshBoard()
  }, [refreshBoard])

  // Picking a ticket shows its newest run: live if it's the one running, otherwise from the audit trail.
  useEffect(() => {
    if (selectedId === null) return
    let cancelled = false
    const load = active && active.ticketId === selectedId
      ? api.events({ root_run_id: active.rootRunId, limit: 500 }).then((r) => r.events)
      : api.events({ ticket_id: selectedId, limit: 500 }).then((r) => latestRun(r.events))
    load
      .then((run) => {
        if (cancelled) return
        setEvents(run)
        if (run[0]) rememberRun(run[0].root_run_id)
      })
      .catch((err) => setToast({ kind: 'error', text: message(err) }))
    return () => {
      cancelled = true
    }
  }, [selectedId, active, rememberRun])

  // While a run is going: pull new events, check whether it finished, keep tickets fresh.
  useEffect(() => {
    if (!active) return
    let stopped = false
    let tick = 0
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        const res = await api.events({ root_run_id: active.rootRunId, since: since.current, limit: 500 })
        since.current = res.next_since
        if (res.events.length && selectedRef.current === active.ticketId) {
          setEvents((prev) => merge(prev, res.events, active.rootRunId))
        }
        tick += 1
        if (tick % 2 === 0) {
          const info = await api.run(active.rootRunId)
          if (info.status !== 'running') {
            stopped = true
            setRuns((r) => ({ ...r, [info.root_run_id]: info }))
            const last = await api.events({ root_run_id: active.rootRunId, limit: 500 })
            if (selectedRef.current === active.ticketId) setEvents(last.events)
            setActive(null)
            await refreshBoard()
            setToast(
              info.status === 'done'
                ? { kind: 'ok', text: `Ticket #${info.ticket_id}: the team finished. ${info.decision?.final_status === 'resolved' ? 'Resolved.' : 'Check the approvals.'}` }
                : { kind: 'error', text: `Ticket #${info.ticket_id} run failed: ${info.error}` },
            )
            return
          }
        }
        if (tick % 4 === 0) void refreshBoard()
      } catch (err) {
        setToast({ kind: 'error', text: message(err) })
      }
      if (!stopped) timer = setTimeout(poll, POLL_MS)
    }
    timer = setTimeout(poll, 400)
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [active, refreshBoard])

  // When nothing is running, refresh now and then so approvals made elsewhere show up.
  useEffect(() => {
    if (active) return
    const t = setInterval(() => document.visibilityState === 'visible' && void refreshBoard(), IDLE_REFRESH_MS)
    return () => clearInterval(t)
  }, [active, refreshBoard])

  const startRun = async (ticketId: number) => {
    try {
      const r = await api.runTicket(ticketId)
      since.current = 0
      setEvents([])
      setActive({ rootRunId: r.root_run_id, ticketId })
      void refreshBoard()
    } catch (err) {
      setToast({ kind: 'error', text: message(err) })
    }
  }

  const approve = async (a: Approval) => {
    try {
      const res = await api.approve(a.id, approver.trim())
      await refreshBoard(`${APPROVAL_LABEL[a.kind]} #${a.id}`)
      const resolved = res.ticket_status === 'resolved' ? ' The ticket is now resolved.' : ''
      setToast({ kind: 'ok', text: a.cash_out ? `Paid ${money(a.amount)} (#${a.id}).${resolved}` : `Approved #${a.id}.${resolved}` })
    } catch (err) {
      setToast({ kind: 'error', text: `Not approved: ${message(err)}` })
      void refreshBoard()
    }
  }

  const reject = async (a: Approval, note: string) => {
    try {
      const res = await api.reject(a.id, approver.trim(), note.trim())
      await refreshBoard()
      setToast({ kind: 'ok', text: `Rejected #${a.id}.${res.ticket_status === 'resolved' ? ' The ticket is now resolved.' : ''}` })
    } catch (err) {
      setToast({ kind: 'error', text: `Not rejected: ${message(err)}` })
    }
  }

  const reset = async () => {
    if (!window.confirm('Reset the board? Tickets, cash, invoices and leases go back to their original values and all approvals and drafts are cleared. The audit trail is kept.')) return
    try {
      await api.reset()
      const h = await api.health()
      setLastReset(h.last_reset_at)
      await refreshBoard('board reset')
      setToast({ kind: 'ok', text: 'Board reset to the original data.' })
    } catch (err) {
      setToast({ kind: 'error', text: message(err) })
    }
  }

  const selected = tickets.find((t) => t.id === selectedId) ?? null
  const root = events[0]?.root_run_id ?? null
  const live = !!active && active.ticketId === selectedId
  const stale = !live && !!root && !!lastReset && events[0].timestamp < lastReset
  const bossAnswer = events.find((e) => e.event === 'run_end' && e.depth === 0)?.answer ?? null
  // Cash only goes out, and only through approvals, so the opening balance is what's left plus what was paid.
  const paid = tickets.flatMap((t) => t.approvals).filter((a) => a.cash_out && a.status === 'paid').reduce((sum, a) => sum + a.amount, 0)
  const opening = (cash?.balance ?? 0) + paid

  return (
    <div className="app">
      <Confetti burst={party?.key ?? 0} />
      <Header
        dateToday={dateToday}
        cash={cash}
        opening={opening}
        preview={preview}
        cashChange={cashChange}
        backendUp={backendUp}
        model={model}
        busy={!!active}
        onReset={() => void reset()}
      />
      <TeamBar events={events} live={live} dancing={party?.agent ?? null} filter={agentFilter} onFilter={setAgentFilter} />
      {party && (
        <div className="party-banner" role="status" onClick={() => setParty(null)}>
          <span className="party-dan"><HandsomeDan agent={party.agent} mood="happy" size={56} /></span>
          <div>
            <strong>Ticket #{party.ticketId} resolved!</strong>
            <span>{party.agent} closed it out. 🎉</span>
          </div>
        </div>
      )}
      {toast && (
        <div className={`toast ${toast.kind}`} role="status" onClick={() => setToast(null)}>
          {toast.text}
        </div>
      )}
      <div className="layout">
        <TicketList tickets={tickets} selectedId={selectedId} runningId={active?.ticketId ?? null} onSelect={setSelectedId} />
        <main className="workspace">
          {selected ? (
            <>
              <TicketHeader ticket={selected} running={live} otherRunning={!!active && !live} onRun={() => void startRun(selected.id)} />
              <Approvals approvals={selected.approvals} approver={approver} onApproverChange={setApprover} onApprove={approve} onReject={reject} onPreview={setPreview} />
              <div className="columns">
                <AgentFeed events={events} live={live} stale={stale} startedAt={events[0]?.timestamp ?? null} agentFilter={agentFilter} onClearFilter={() => setAgentFilter(null)} />
                <aside className="side">
                  {!live && !stale && <BossCall decision={root ? runs[root]?.decision ?? null : null} answer={bossAnswer} />}
                  <AgentSummary events={events} live={live} />
                  <Drafts drafts={selected.drafts} />
                  <BoardNotes updates={selected.updates} />
                </aside>
              </div>
            </>
          ) : (
            <p className="empty">{backendUp === false ? 'The backend is offline. Start it with uvicorn main:app --reload --port 8000.' : 'Loading tickets…'}</p>
          )}
        </main>
      </div>
    </div>
  )
}
