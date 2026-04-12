import { formatUSD, formatPercent } from "../utils/formatters"

export default function DumpCalculator({ data }) {
  if (!data || data.dump_price_impact_percent === 0) return null

  const impactColor = data.dump_price_impact_percent > 50
    ? 'var(--red-400)'
    : data.dump_price_impact_percent > 20
    ? 'var(--orange-400)'
    : 'var(--yellow-400)'

  return (
    <div className="card animate-fade-in-up">
      <div className="card-header">
        <span style={{ fontSize: '1rem' }}>📉</span>
        <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>Dump Impact Calculator</span>
      </div>
      <div style={{ padding: 'var(--space-5) var(--space-6)' }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr auto 1fr',
          alignItems: 'center', gap: 'var(--space-6)',
          textAlign: 'center',
        }}>
          {/* Before */}
          <div>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Your Investment
            </p>
            <p style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--green-400)', fontFamily: 'var(--font-mono)' }}>
              {formatUSD(data.investment_amount || 100)}
            </p>
          </div>

          {/* Arrow */}
          <div style={{ color: impactColor, fontSize: '1.5rem' }}>→</div>

          {/* After */}
          <div>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              After Dump
            </p>
            <p style={{ fontSize: '1.5rem', fontWeight: 700, color: impactColor, fontFamily: 'var(--font-mono)' }}>
              {formatUSD(data.investment_value_after_dump)}
            </p>
          </div>
        </div>

        {/* Impact bar */}
        <div style={{ marginTop: 'var(--space-5)' }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', marginBottom: 6,
          }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Price Impact</span>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: impactColor, fontFamily: 'var(--font-mono)' }}>
              -{formatPercent(data.dump_price_impact_percent)}
            </span>
          </div>
          <div style={{
            height: 6, background: 'var(--bg-surface)', borderRadius: 'var(--radius-full)',
            overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${Math.min(data.dump_price_impact_percent, 100)}%`,
              background: impactColor,
              borderRadius: 'var(--radius-full)',
              transition: 'width 1s cubic-bezier(0.16, 1, 0.3, 1)',
            }} />
          </div>
        </div>
      </div>
    </div>
  )
}
