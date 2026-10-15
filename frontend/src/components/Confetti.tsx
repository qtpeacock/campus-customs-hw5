import { useEffect, useRef } from 'react'

const COLORS = ['#0b4fa8', '#3d8bf2', '#062a5c', '#8ec5ff', '#1d63c9', '#0b0b0c', '#bcd9ff']
const DURATION_MS = 2600

/** A quick burst of confetti across the screen. Skipped for people who ask for reduced motion. */
export function Confetti({ burst }: { burst: number }) {
  const canvas = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!burst || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const c = canvas.current
    const ctx = c?.getContext('2d')
    if (!c || !ctx) return
    c.width = window.innerWidth
    c.height = window.innerHeight
    const pieces = Array.from({ length: 170 }, () => ({
      x: c.width * (0.15 + Math.random() * 0.7),
      y: -20 - Math.random() * c.height * 0.3,
      vx: (Math.random() - 0.5) * 9,
      vy: 2 + Math.random() * 6,
      size: 6 + Math.random() * 8,
      spin: Math.random() * Math.PI,
      vspin: (Math.random() - 0.5) * 0.35,
      color: COLORS[Math.floor(Math.random() * COLORS.length)],
      round: Math.random() < 0.3,
    }))
    const start = performance.now()
    let frame = 0
    const draw = (now: number) => {
      const t = now - start
      ctx.clearRect(0, 0, c.width, c.height)
      ctx.globalAlpha = t > DURATION_MS - 600 ? Math.max(0, (DURATION_MS - t) / 600) : 1
      for (const p of pieces) {
        p.vy += 0.12
        p.vx *= 0.99
        p.x += p.vx
        p.y += p.vy
        p.spin += p.vspin
        ctx.save()
        ctx.translate(p.x, p.y)
        ctx.rotate(p.spin)
        ctx.fillStyle = p.color
        if (p.round) {
          ctx.beginPath()
          ctx.arc(0, 0, p.size / 2.4, 0, Math.PI * 2)
          ctx.fill()
        } else {
          ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2)
        }
        ctx.restore()
      }
      if (t < DURATION_MS) frame = requestAnimationFrame(draw)
      else ctx.clearRect(0, 0, c.width, c.height)
    }
    frame = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(frame)
  }, [burst])

  return <canvas ref={canvas} className="confetti" aria-hidden="true" />
}
