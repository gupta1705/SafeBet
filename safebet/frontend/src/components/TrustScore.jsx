import { scoreColor, scoreBandClass } from "../utils/formatters"
import { useEffect, useState } from "react"

export default function TrustScore({ score, band }) {
  const [animatedScore, setAnimatedScore] = useState(0)
  const [mounted, setMounted] = useState(false)
  const color = scoreColor(score)

  useEffect(() => {
    setMounted(true)
    const duration = 1200
    const steps = 60
    const increment = score / steps
    let current = 0
    const timer = setInterval(() => {
      current += increment
      if (current >= score) {
        setAnimatedScore(score)
        clearInterval(timer)
      } else {
        setAnimatedScore(Math.round(current))
      }
    }, duration / steps)
    return () => clearInterval(timer)
  }, [score])

  const radius = 80
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (animatedScore / 100) * circumference

  const isDangerous = score < 30

  return (
    <div className="card animate-fade-in-up" style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 'var(--space-10) var(--space-6)',
      background: `linear-gradient(135deg, var(--bg-card), var(--bg-surface))`,
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Ambient background glow */}
      <div style={{
        position: 'absolute',
        top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        width: 300, height: 300,
        borderRadius: '50%',
        background: `radial-gradient(circle, ${color}08 0%, transparent 70%)`,
        filter: 'blur(40px)',
        animation: isDangerous ? 'pulse-glow 2s ease-in-out infinite' : 'none',
        pointerEvents: 'none',
      }} />

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--space-4)', position: 'relative', zIndex: 1 }}>

        {/* Label */}
        <span style={{
          fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.15em',
          textTransform: 'uppercase', color: 'var(--text-muted)',
        }}>
          Trust Score
        </span>

        {/* Circle */}
        <div style={{ position: 'relative', width: 200, height: 200 }}>
          <svg width="200" height="200" style={{ transform: 'rotate(-90deg)' }}>
            {/* Outer glow ring */}
            <circle
              cx="100" cy="100" r={radius + 8}
              fill="none" stroke={`${color}10`} strokeWidth="2"
              style={{
                animation: isDangerous ? 'pulse-ring 2s ease-in-out infinite' : 'none',
                color: color,
              }}
            />
            {/* Background circle */}
            <circle
              cx="100" cy="100" r={radius}
              fill="none" stroke="var(--border-subtle)" strokeWidth="8"
            />
            {/* Progress circle */}
            <circle
              cx="100" cy="100" r={radius}
              fill="none" stroke={color} strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              style={{
                transition: 'stroke-dashoffset 1.2s cubic-bezier(0.16, 1, 0.3, 1)',
                filter: `drop-shadow(0 0 10px ${color}50)`,
              }}
            />
          </svg>
          {/* Score text in center */}
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
          }}>
            <span style={{
              fontSize: '3rem', fontWeight: 900, color: color,
              lineHeight: 1,
              fontFamily: 'var(--font-mono)',
              textShadow: `0 0 20px ${color}30`,
            }}>
              {animatedScore}
            </span>
            <span style={{
              fontSize: '0.75rem', color: 'var(--text-muted)',
              fontWeight: 500, marginTop: 4,
            }}>
              / 100
            </span>
          </div>
        </div>

        {/* Band */}
        <span className={scoreBandClass(band)} style={{
          fontSize: '0.85rem', fontWeight: 700,
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          padding: '4px 16px',
          borderRadius: 'var(--radius-full)',
          background: `${color}10`,
          border: `1px solid ${color}20`,
        }}>
          {band}
        </span>
      </div>
    </div>
  )
}
