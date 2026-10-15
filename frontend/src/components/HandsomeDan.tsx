import { DAN_GEAR } from '../agents'
import type { AgentName } from '../types'

export type DanMood = 'awake' | 'asleep' | 'happy'

const INK = '#0b0b0c'

/** The hat or gear that tells each Dan apart. */
function Gear({ agent }: { agent: AgentName }) {
  switch (agent) {
    case 'Boss': // a crown
      return (
        <g>
          <path d="M31 27 L35 11 L43 21 L50 6 L57 21 L65 11 L69 27 Z" fill="#3d8bf2" stroke={INK} strokeWidth="2.5" strokeLinejoin="round" />
          <rect x="30" y="24" width="40" height="7" rx="3" fill="#0b4fa8" stroke={INK} strokeWidth="2.5" />
          <circle cx="35" cy="11" r="2.6" fill="#fff" stroke={INK} strokeWidth="1.5" />
          <circle cx="50" cy="6" r="2.6" fill="#fff" stroke={INK} strokeWidth="1.5" />
          <circle cx="65" cy="11" r="2.6" fill="#fff" stroke={INK} strokeWidth="1.5" />
        </g>
      )
    case 'Inventory': // a warehouse beanie with a pompom
      return (
        <g>
          <path d="M22 36 Q24 10 50 10 Q76 10 78 36 Z" fill="#0b4fa8" stroke={INK} strokeWidth="2.5" />
          <rect x="20" y="30" width="60" height="9" rx="4.5" fill="#8ec5ff" stroke={INK} strokeWidth="2.5" />
          <circle cx="50" cy="8" r="5.5" fill="#fff" stroke={INK} strokeWidth="2.5" />
        </g>
      )
    case 'Accounting': // a green-eyeshade visor (in navy) and round glasses
      return (
        <g>
          <path d="M20 36 Q50 20 80 36 L74 42 Q50 31 26 42 Z" fill="#062a5c" stroke={INK} strokeWidth="2.5" strokeLinejoin="round" />
          <circle cx="38" cy="51" r="8.5" fill="rgba(255,255,255,0.35)" stroke={INK} strokeWidth="2.5" />
          <circle cx="62" cy="51" r="8.5" fill="rgba(255,255,255,0.35)" stroke={INK} strokeWidth="2.5" />
          <path d="M46.5 50 Q50 47 53.5 50" fill="none" stroke={INK} strokeWidth="2.5" />
        </g>
      )
    case 'Facilities': // a hard hat
      return (
        <g>
          <path d="M24 34 Q25 11 50 11 Q75 11 76 34 Z" fill="#1d63c9" stroke={INK} strokeWidth="2.5" />
          <rect x="16" y="31" width="68" height="7" rx="3.5" fill="#1d63c9" stroke={INK} strokeWidth="2.5" />
          <path d="M50 12 L50 31" stroke="#fff" strokeWidth="4" strokeLinecap="round" />
        </g>
      )
    case 'Customer Service': // a headset with a mic
      return (
        <g>
          <path d="M18 52 Q16 14 50 14 Q84 14 82 52" fill="none" stroke={INK} strokeWidth="4.5" strokeLinecap="round" />
          <rect x="11" y="44" width="11" height="17" rx="5" fill="#3d8bf2" stroke={INK} strokeWidth="2.5" />
          <rect x="78" y="44" width="11" height="17" rx="5" fill="#3d8bf2" stroke={INK} strokeWidth="2.5" />
          <path d="M17 60 Q20 78 36 79" fill="none" stroke={INK} strokeWidth="3" strokeLinecap="round" />
          <circle cx="37" cy="79" r="3.6" fill={INK} />
        </g>
      )
  }
}

function Eyes({ mood }: { mood: DanMood }) {
  if (mood === 'asleep')
    return (
      <g fill="none" stroke={INK} strokeWidth="2.6" strokeLinecap="round">
        <path d="M33 52 Q38 56 43 52" />
        <path d="M57 52 Q62 56 67 52" />
      </g>
    )
  if (mood === 'happy')
    return (
      <g fill="none" stroke={INK} strokeWidth="3" strokeLinecap="round">
        <path d="M33 53 Q38 46 43 53" />
        <path d="M57 53 Q62 46 67 53" />
      </g>
    )
  return (
    <g>
      <circle cx="38" cy="51" r="4.6" fill={INK} />
      <circle cx="62" cy="51" r="4.6" fill={INK} />
      <circle cx="39.6" cy="49.4" r="1.6" fill="#fff" />
      <circle cx="63.6" cy="49.4" r="1.6" fill="#fff" />
    </g>
  )
}

/**
 * A little Handsome Dan (the Yale bulldog), drawn in SVG: white face, droopy ears,
 * a grey patch, a big nose and the classic bulldog underbite. Each agent wears its own
 * gear and collar colour, so they're easy to tell apart even in black and white.
 */
export function HandsomeDan({ agent, mood = 'awake', size = 64 }: { agent: AgentName; mood?: DanMood; size?: number }) {
  const { collar } = DAN_GEAR[agent]
  const gearOnTop = agent !== 'Customer Service' && agent !== 'Accounting'
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} role="img" aria-label={`${agent} (Handsome Dan)`}>
      {/* ears */}
      <path d="M22 36 Q6 38 10 60 Q18 54 30 46 Z" fill="#2b3240" stroke={INK} strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M78 36 Q94 38 90 60 Q82 54 70 46 Z" fill="#2b3240" stroke={INK} strokeWidth="2.5" strokeLinejoin="round" />
      {/* collar */}
      <rect x="27" y="83" width="46" height="9" rx="4.5" fill={collar} stroke={INK} strokeWidth="2.5" />
      <circle cx="50" cy="94" r="4" fill="#fff" stroke={INK} strokeWidth="2" />
      {/* head */}
      <ellipse cx="50" cy="58" rx="34" ry="29" fill="#ffffff" stroke={INK} strokeWidth="3" />
      {/* patch over one eye */}
      <ellipse cx="63" cy="50" rx="11" ry="10" fill="#c9d9f0" />
      {/* brow wrinkles */}
      <path d="M38 39 Q50 34 62 39" fill="none" stroke="#9aa6b8" strokeWidth="2" strokeLinecap="round" />
      <path d="M42 43.5 Q50 40.5 58 43.5" fill="none" stroke="#9aa6b8" strokeWidth="2" strokeLinecap="round" />
      {!gearOnTop && <Gear agent={agent} />}
      <Eyes mood={mood} />
      {/* muzzle, nose, jowls and underbite */}
      <ellipse cx="50" cy="70" rx="19" ry="12.5" fill="#f1f5fb" stroke={INK} strokeWidth="2.2" />
      <ellipse cx="50" cy="62.5" rx="7.5" ry="5" fill={INK} />
      <ellipse cx="47.5" cy="61" rx="2.2" ry="1.2" fill="#fff" opacity="0.7" />
      <path d="M33 72 Q41 81 50 74 Q59 81 67 72" fill="none" stroke={INK} strokeWidth="2.6" strokeLinecap="round" />
      <path d="M43.5 75 L45.5 69.5 L47.5 75 Z" fill="#fff" stroke={INK} strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M52.5 75 L54.5 69.5 L56.5 75 Z" fill="#fff" stroke={INK} strokeWidth="1.6" strokeLinejoin="round" />
      {gearOnTop && <Gear agent={agent} />}
    </svg>
  )
}
