// Shapes of what the FastAPI backend (backend/main.py) returns.

export type AgentName = 'Boss' | 'Inventory' | 'Accounting' | 'Facilities' | 'Customer Service'
export type TicketStatus = 'open' | 'in_progress' | 'waiting_approval' | 'resolved'

export interface Approval {
  id: number
  kind: 'invoice_payment' | 'rent_payment' | 'purchase_order' | 'price_override'
  ref_id: number | null
  sku: string | null
  size: string | null
  qty: number | null
  unit_price: number | null
  amount: number
  cash_out: number
  status: 'pending' | 'approved' | 'rejected' | 'paid'
  requested_by: AgentName
  reason: string
}

export interface Draft {
  id: number
  recipient: string
  subject: string
  body: string
  written_by: string
  status: string
}

export interface TicketUpdate {
  agent: string
  status_before: string | null
  status_after: string | null
  note: string
  created_at: string
}

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: TicketStatus
  state: 'open' | 'resolved'
  notes: string | null
  created_at: string
  approvals: Approval[]
  drafts: Draft[]
  updates: TicketUpdate[]
}

export interface TicketsResponse {
  date_today: string
  count: number
  tickets: Ticket[]
}

export interface Cash {
  account: string
  balance: number
  balance_date: string
  already_committed: number
  available: number
  committed_requests: { id: number; ticket_id: number; kind: string; amount: number; status: string }[]
  date_today: string
}

export type EventKind =
  | 'run_start'
  | 'model_response'
  | 'tool_call'
  | 'tool_result'
  | 'retry'
  | 'delegation_refused'
  | 'run_end'
  | 'run_error'

export interface AgentEvent {
  index: number
  timestamp: string
  agent: AgentName
  depth: number
  ticket_id: number | null
  root_run_id: string
  run_id: string
  parent_run_id: string | null
  event: EventKind
  tool_name: string | null
  tool_args: string | null
  teammate: AgentName | null
  text: string | null
  answer: string | null
  summary: string
}

export interface EventsResponse {
  events: AgentEvent[]
  next_since: number
  total: number
}

export interface BossDecision {
  ticket_id: number | null
  final_status: TicketStatus
  decision: string
  summary: string
  teammates_consulted: AgentName[]
  approval_ids: number[]
  draft_ids: number[]
  needs_human: string[]
  next_steps: string[]
}

export interface RunInfo {
  root_run_id: string
  ticket_id: number
  status: 'running' | 'done' | 'failed'
  started_at: string
  finished_at: string | null
  decision: BossDecision | null
  error: string | null
}

export interface Health {
  ok: boolean
  model: string
  database: string
  run_in_progress: string | null
  last_reset_at: string | null
}
