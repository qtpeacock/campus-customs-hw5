// Every call the desk makes goes to the FastAPI backend from Problem 7.
import type { Cash, EventsResponse, Health, RunInfo, TicketsResponse } from './types'

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** FastAPI puts the reason in `detail`: a string, a refusal object with `error`, or validation errors. */
function reason(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && 'error' in detail) return String((detail as { error: unknown }).error)
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg)
  return fallback
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_BASE}. Is uvicorn running?`)
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, reason(body?.detail, `${res.status} ${res.statusText}`))
  return body as T
}

export const api = {
  health: () => call<Health>('/api/health'),
  tickets: () => call<TicketsResponse>('/api/tickets'),
  cash: () => call<Cash>('/api/cash'),
  runTicket: (id: number) =>
    call<{ root_run_id: string; ticket_id: number; status: string }>(`/api/tickets/${id}/run`, { method: 'POST' }),
  run: (rootRunId: string) => call<RunInfo>(`/api/runs/${encodeURIComponent(rootRunId)}`),
  runs: () => call<{ runs: RunInfo[] }>('/api/runs'),
  events: (params: { since?: number; limit?: number; ticket_id?: number; root_run_id?: string }) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => v !== undefined && q.set(k, String(v)))
    return call<EventsResponse>(`/api/events?${q}`)
  },
  approve: (id: number, approved_by: string) =>
    call<Record<string, unknown>>(`/api/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by }),
    }),
  reject: (id: number, decided_by: string, note: string) =>
    call<Record<string, unknown>>(`/api/approvals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ decided_by, note }),
    }),
  reset: () => call<{ ok: boolean; identical_to_original: boolean }>('/api/reset', { method: 'POST' }),
}
