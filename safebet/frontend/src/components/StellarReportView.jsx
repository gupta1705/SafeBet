import TheCatch from "./TheCatch"
import TheVerdict from "./TheVerdict"

/**
 * Determines the RiskFlag-compatible status + display value for a Stellar boolean flag.
 *  - isGood=true  → flag being true is SAFE, being false is WARNING
 *  - isGood=false → flag being true is DANGER, being false is SAFE
 *  - isGood=null  → always INFO
 */
function flagProps(flagValue, isGood) {
  const displayValue = flagValue ? "TRUE" : "FALSE"
  if (isGood === null) return { status: "INFO", displayValue }
  if (isGood)  return { status: flagValue ? "SAFE" : "WARNING", displayValue }
  return { status: flagValue ? "DANGER" : "SAFE", displayValue }
}

function StellarFlag({ label, flagValue, isGood, description }) {
  const { status, displayValue } = flagProps(flagValue, isGood)
  const dotColors = {
    DANGER: "var(--red-400)", WARNING: "var(--yellow-400)",
    SAFE: "var(--green-400)", INFO: "var(--blue-400)",
  }
  const dot = dotColors[status] || dotColors.INFO
  const badgeBg = {
    DANGER: "rgba(239, 68, 68, 0.12)", WARNING: "rgba(234, 179, 8, 0.12)",
    SAFE: "rgba(34, 197, 94, 0.12)", INFO: "rgba(96, 165, 250, 0.12)",
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--border-subtle)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: dot, flexShrink: 0 }} />
        <div>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{label}</span>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2, lineHeight: 1.4 }}>{description}</p>
        </div>
      </div>
      <span style={{
        fontSize: '0.65rem', fontWeight: 600, padding: '3px 8px',
        borderRadius: '4px', background: badgeBg[status], color: dot,
        letterSpacing: '0.04em', flexShrink: 0,
      }}>
        {displayValue}
      </span>
    </div>
  )
}

export default function StellarReportView({ data }) {
  const riskBadge = {
    HIGH: { bg: 'rgba(239, 68, 68, 0.15)', color: 'var(--red-400)' },
    MODERATE: { bg: 'rgba(234, 179, 8, 0.15)', color: 'var(--yellow-400)' },
    LOW: { bg: 'rgba(34, 197, 94, 0.15)', color: 'var(--green-400)' },
    UNKNOWN: { bg: 'rgba(156, 163, 175, 0.15)', color: 'var(--text-muted)' },
  }
  const badge = riskBadge[data.risk_level] || riskBadge.UNKNOWN

  return (
    <div className="stagger" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
      {/* ── Overview ───────────────────────────────────────── */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Stellar Issuer Risk Profile</h2>
          <span style={{ backgroundColor: badge.bg, color: badge.color, padding: '4px 10px', borderRadius: '4px', fontWeight: 700, fontSize: '0.75rem', letterSpacing: '0.04em' }}>
            {data.risk_level} RISK
          </span>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          {data.risk_details.map((detail, idx) => (
            <p key={idx} style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.5 }}>
              • {detail}
            </p>
          ))}
        </div>
      </div>

      <TheCatch text={data.the_catch} />
      <TheVerdict text={data.verdict} />

      {/* ── Account Flags ─────────────────────────────────────── */}
      <div className="card">
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 'var(--space-4)' }}>Account Flags</h3>
        <StellarFlag
          label="Auth Immutable"
          flagValue={data.flags.auth_immutable}
          isGood={true}
          description="If true, flags are locked permanently and can never be changed."
        />
        <StellarFlag
          label="Auth Revocable (Freeze Power)"
          flagValue={data.flags.auth_revocable}
          isGood={false}
          description="If true, the issuer can freeze tokens in holders' wallets."
        />
        <StellarFlag
          label="Auth Clawback Enabled"
          flagValue={data.flags.auth_clawback_enabled}
          isGood={false}
          description="If true, the issuer can claw back (remove) tokens from wallets."
        />
        <StellarFlag
          label="Auth Required"
          flagValue={data.flags.auth_required}
          isGood={null}
          description="If true, you must be explicitly approved by the issuer to hold the asset."
        />
      </div>

      {/* ── Metadata & Assets ───────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-5)' }}>
        <div className="card">
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 'var(--space-3)' }}>Issuer Info</h3>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Home Domain</span>
            <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{data.home_domain || "Not set"}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Is Multi-Sig</span>
            <span style={{ color: data.is_multisig ? 'var(--green-400)' : 'var(--text-primary)', fontWeight: 500 }}>{data.is_multisig ? "Yes" : "No"}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Signers</span>
            <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{data.num_signers}</span>
          </div>
        </div>

        <div className="card">
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 'var(--space-3)' }}>Issued Assets ({data.assets.length})</h3>
          {data.assets.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {data.assets.map((asset, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', background: 'var(--bg-hover)', padding: '8px 12px', borderRadius: '4px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{asset.asset_code}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>{asset.num_accounts} holders</span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)' }}>No assets issued.</p>
          )}
        </div>
      </div>

    </div>
  )
}
