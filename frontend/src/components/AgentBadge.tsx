import { AGENTS } from '../agents'
import type { AgentName } from '../types'

export function AgentBadge({ agent, size = 'md' }: { agent: AgentName; size?: 'sm' | 'md' | 'lg' }) {
  const meta = AGENTS[agent]
  return (
    <span className={`agent-badge ${meta.cls} badge-${size}`} title={`${agent}: ${meta.role}`} aria-hidden="true">
      {meta.badge}
    </span>
  )
}
