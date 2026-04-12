export default function TheCatch({ text }) {
  if (!text) return null

  return (
    <div className="animate-fade-in-up" style={{
      padding: 'var(--space-5) var(--space-6)',
      background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.08), rgba(239, 68, 68, 0.02))',
      border: '1px solid rgba(239, 68, 68, 0.18)',
      borderRadius: 'var(--radius-lg)',
      borderLeft: '3px solid var(--red-400)',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Subtle scan line effect */}
      <div style={{
        position: 'absolute',
        left: 0, right: 0,
        height: 1,
        background: 'linear-gradient(90deg, transparent, rgba(239, 68, 68, 0.3), transparent)',
        animation: 'scanLine 4s linear infinite',
        pointerEvents: 'none',
      }} />

      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)',
        position: 'relative', zIndex: 1,
      }}>
        <span style={{ fontSize: '1.1rem', flexShrink: 0, marginTop: 1 }}>⚠️</span>
        <div>
          <p style={{
            fontSize: '0.7rem', fontWeight: 700, color: 'var(--red-400)',
            textTransform: 'uppercase', letterSpacing: '0.1em',
            marginBottom: 'var(--space-2)',
          }}>
            The Catch
          </p>
          <p style={{
            fontSize: '0.95rem', color: 'var(--red-200)',
            fontWeight: 500, lineHeight: 1.6,
          }}>
            {text}
          </p>
        </div>
      </div>
    </div>
  )
}
