import { useState } from "react"

const STATUS_CONFIG = {
  DANGER:  { dot: "dot-red",    badgeClass: "badge-danger",  label: "DANGER",  accent: "var(--red-400)",    glow: "rgba(239, 68, 68, 0.08)" },
  WARNING: { dot: "dot-yellow", badgeClass: "badge-warning", label: "WARNING", accent: "var(--yellow-400)", glow: "rgba(234, 179, 8, 0.08)" },
  SAFE:    { dot: "dot-green",  badgeClass: "badge-safe",    label: "SAFE",    accent: "var(--green-400)",  glow: "rgba(34, 197, 94, 0.08)" },
  INFO:    { dot: "dot-blue",   badgeClass: "badge-info",    label: "INFO",    accent: "var(--blue-400)",   glow: "rgba(59, 130, 246, 0.08)" },
  PENDING: { dot: "",           badgeClass: "badge-pending", label: "PENDING", accent: "var(--text-muted)", glow: "rgba(107, 114, 128, 0.08)" },
}

export default function RiskFlag({ label, status, value, explanation, brief, decisionImpact }) {
  const [open, setOpen] = useState(false)
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.INFO
  const hasExpand = explanation || decisionImpact
  const isSafe = status === "SAFE"

  return (
    <div style={{
      borderBottom: '1px solid var(--border-subtle)',
      borderLeft: `2px solid ${open ? config.accent : 'transparent'}`,
      transition: 'border-left-color var(--transition-fast)',
    }}>
      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: 'var(--space-4) var(--space-5)',
          cursor: hasExpand ? 'pointer' : 'default',
          transition: 'background var(--transition-fast)',
        }}
        onClick={() => hasExpand && setOpen(!open)}
        onMouseEnter={e => { if (hasExpand) e.currentTarget.style.background = 'var(--bg-hover)' }}
        onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
      >
        {/* Left: dot + label + brief */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)', flex: 1, minWidth: 0 }}>
          <div className={`dot ${config.dot}`} style={{ marginTop: 5 }} />
          <div style={{ minWidth: 0 }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
              {label}
            </span>
            {brief && (
              <p className="flag-brief">{brief}</p>
            )}
          </div>
        </div>

        {/* Right: value + expand arrow */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flexShrink: 0, marginLeft: 'var(--space-3)' }}>
          <span className={`badge ${config.badgeClass}`} style={{ fontSize: '0.65rem' }}>
            {value}
          </span>
          {hasExpand && (
            <span style={{
              color: 'var(--text-disabled)', fontSize: '0.6rem',
              transition: 'transform var(--transition-fast)',
              transform: open ? 'rotate(180deg)' : 'none',
            }}>
              ▼
            </span>
          )}
        </div>
      </div>

      {/* Expandable section */}
      {open && hasExpand && (
        <div style={{
          padding: '0 var(--space-5) var(--space-4)',
          paddingLeft: 'calc(var(--space-5) + 8px + var(--space-3))',
          animation: 'fadeIn 0.25s ease-out',
        }}>
          {/* Explanation */}
          {explanation && (
            <p style={{
              fontSize: '0.8rem', color: 'var(--text-muted)',
              lineHeight: 1.65,
              borderLeft: `2px solid ${config.accent}`,
              paddingLeft: 'var(--space-4)',
              marginBottom: decisionImpact ? 'var(--space-3)' : 0,
            }}>
              {explanation}
            </p>
          )}

          {/* Decision Impact */}
          {decisionImpact && (
            <div className={`flag-impact ${isSafe ? 'flag-impact-safe' : ''}`}>
              <span className="flag-impact-label">
                {isSafe ? '✓ Impact' : '🎯 Impact'}
              </span>
              <span className="flag-impact-text">{decisionImpact}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
