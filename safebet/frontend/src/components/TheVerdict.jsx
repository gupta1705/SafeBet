export default function TheVerdict({ text }) {
  if (!text) return null

  return (
    <div className="card animate-fade-in-up" style={{
      padding: 'var(--space-5) var(--space-6)',
      borderLeft: '3px solid var(--text-muted)',
    }}>
      <p style={{
        fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted)',
        textTransform: 'uppercase', letterSpacing: '0.12em',
        marginBottom: 'var(--space-3)',
        display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
      }}>
        <span style={{ fontSize: '0.85rem' }}>📋</span>
        AI Verdict
      </p>
      <p style={{
        fontSize: '0.95rem', color: 'var(--text-secondary)',
        lineHeight: 1.7,
      }}>
        {text}
      </p>
    </div>
  )
}
