import type { AgentEvent, AgentName, Approval, TicketStatus } from './types'

/** How each agent reads on the board: badge letters, one-line role, and a style class. */
export const AGENTS: Record<AgentName, { badge: string; role: string; cls: string }> = {
  Boss: { badge: 'B', role: 'Reads the ticket, routes work, makes the final call', cls: 'agent-boss' },
  Inventory: { badge: 'IN', role: 'Stock by size, vendors, lead times', cls: 'agent-inventory' },
  Accounting: { badge: 'AC', role: 'Cash, invoices, margins, approval requests', cls: 'agent-accounting' },
  Facilities: { badge: 'FA', role: 'Leases, rent, the shop space', cls: 'agent-facilities' },
  'Customer Service': { badge: 'CS', role: 'Drafts replies (never sent)', cls: 'agent-cs' },
}

export const AGENT_ORDER: AgentName[] = ['Boss', 'Inventory', 'Accounting', 'Facilities', 'Customer Service']

/** Each Handsome Dan's collar colour and the hat/gear that tells them apart. */
export const DAN_GEAR: Record<AgentName, { collar: string; gear: string }> = {
  Boss: { collar: '#0b0b0c', gear: 'crown' },
  Inventory: { collar: '#0b4fa8', gear: 'beanie' },
  Accounting: { collar: '#062a5c', gear: 'visor and glasses' },
  Facilities: { collar: '#1d63c9', gear: 'hard hat' },
  'Customer Service': { collar: '#3d8bf2', gear: 'headset' },
}

/** Plain-English names for the MCP tools, so the feed reads like a story, not a log. */
export const TOOL_LABEL: Record<string, string> = {
  get_shop_date: "Checked today's date",
  list_tickets: 'Looked over the board',
  get_ticket: 'Read the ticket',
  check_stock: 'Checked the shelves',
  get_pricing: 'Checked price & margin',
  list_vendors: 'Looked up vendors',
  get_invoice: 'Pulled an invoice',
  list_unpaid_invoices: 'Listed unpaid bills',
  get_lease: 'Read the lease',
  get_cash_position: 'Checked the cash',
  list_approvals: 'Checked approvals',
  request_payment: 'Asked you to approve a payment',
  request_purchase_order: 'Asked you to approve an order',
  request_price_override: 'Asked you to approve a discount',
  draft_customer_message: 'Drafted a message',
  add_ticket_note: 'Left a note on the ticket',
  set_ticket_status: 'Moved the ticket',
}
export const toolLabel = (tool: string | null) => (tool ? TOOL_LABEL[tool] ?? tool : '')

const HIDDEN_ARGS = ['reason', 'body', 'note', 'task', 'agent', 'requested_by', 'written_by']

/** The tool's arguments as short "key value" pairs. The audit trail shortens long arguments,
 *  so when the JSON is cut off, read the complete simple pairs out of it instead. */
export function toolArgs(rawArgs: string | null): string {
  if (!rawArgs) return ''
  let pairs: [string, unknown][]
  try {
    pairs = Object.entries(JSON.parse(rawArgs) as Record<string, unknown>)
  } catch {
    pairs = [...rawArgs.matchAll(/"(\w+)":\s*("(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?|true|false|null)(?=\s*[,}])/g)].map(
      ([, k, v]) => [k, JSON.parse(v)],
    )
  }
  return pairs
    .filter(([k]) => !HIDDEN_ARGS.includes(k))
    .map(([k, v]) => `${k.replace(/_/g, ' ')} ${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(' · ')
}

export const TICKET_TYPE: Record<string, { label: string; icon: string }> = {
  customer_order: { label: 'Customer order', icon: '👕' },
  rent_notice: { label: 'Rent notice', icon: '🏠' },
  price_override: { label: 'Price override', icon: '🏷️' },
}

export const STATUS_LABEL: Record<TicketStatus, string> = {
  open: 'Open',
  in_progress: 'In progress',
  waiting_approval: 'Needs your approval',
  resolved: 'Resolved',
}

export const APPROVAL_LABEL: Record<Approval['kind'], string> = {
  invoice_payment: 'Pay vendor invoice',
  rent_payment: 'Pay rent',
  purchase_order: 'Purchase order',
  price_override: 'Price override',
}

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
export const money = (n: number) => usd.format(n)

export function shopDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
}

export function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit' })
}

export function when(iso: string): string {
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

/** "check_stock" + '{"sku": "X", "size": "S"}' -> "check_stock · sku X · size S" (args may be cut short). */
export function toolLine(tool: string, rawArgs: string | null): string {
  if (!rawArgs) return tool
  try {
    const args = JSON.parse(rawArgs) as Record<string, unknown>
    const parts = Object.entries(args)
      .filter(([k]) => !['reason', 'body', 'note', 'task'].includes(k))
      .map(([k, v]) => `${k} ${typeof v === 'string' ? v : JSON.stringify(v)}`)
    return parts.length ? `${tool} · ${parts.join(' · ')}` : tool
  } catch {
    return `${tool} · ${rawArgs.slice(0, 80)}`
  }
}

/** An agent's one-line answer when it finished. Older audit entries only have the
 *  shortened JSON output, so fall back to reading `answer` / `decision` out of it. */
export function answerOf(e: AgentEvent): string | null {
  return e.answer ?? stringArg(e.text, 'answer') ?? stringArg(e.text, 'decision') ?? e.text
}

/** Pull the inside of a shortened JSON string argument, e.g. the task in an ask_teammate call. */
export function stringArg(raw: string | null, key: string): string | null {
  const m = raw?.match(new RegExp(`"${key}":\\s*"((?:[^"\\\\]|\\\\.)*)`))
  return m ? m[1].replace(/\\"/g, '"').replace(/\\n/g, ' ') : null
}
