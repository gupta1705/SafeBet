import { useLocation, useNavigate } from "react-router-dom"
import TrustScore from "../components/TrustScore"
import TheCatch from "../components/TheCatch"
import TheVerdict from "../components/TheVerdict"
import Module1Control from "../components/Module1Control"
import Module2Traps from "../components/Module2Traps"
import Module3Collapse from "../components/Module3Collapse"
import StellarReportView from "../components/StellarReportView"
import { shortAddress } from "../utils/formatters"

export default function Report() {
  const location = useLocation()
  const navigate = useNavigate()
  const data = location.state?.data

  if (!data) {
    navigate("/")
    return null
  }

  const isStellar = !!data.issuer_address

  if (isStellar) {
    return (
      <div className="page" style={{ paddingTop: 'var(--space-8)', paddingBottom: 'var(--space-16)' }}>
        <div className="container">
          <div className="animate-fade-in" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 'var(--space-8)' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
                <h1 style={{ fontSize: '1.6rem', fontWeight: 800 }}>Stellar Asset Issuer</h1>
                <span className="badge badge-info" style={{ backgroundColor: '#6366f1', color: '#ffffff' }}>STELLAR</span>
              </div>
              <p className="mono text-muted" style={{ fontSize: '0.75rem', wordBreak: 'break-all' }}>
                {data.issuer_address}
              </p>
            </div>
            <button className="btn btn-ghost" onClick={() => navigate("/")} style={{ fontSize: '0.8rem', padding: '8px 16px', flexShrink: 0 }}>
              ← New Scan
            </button>
          </div>

          <StellarReportView data={data} />

          <p style={{ textAlign: 'center', color: 'var(--text-disabled)', fontSize: '0.7rem', marginTop: 'var(--space-12)' }}>
            Scanned in {data.scan_duration_seconds}s · Data read directly from Stellar Horizon
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="page" style={{ paddingTop: 'var(--space-8)', paddingBottom: 'var(--space-16)' }}>
      <div className="container">

        {/* ── Header ───────────────────────────────────────── */}
        <div className="animate-fade-in" style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: 'var(--space-6)',
          padding: 'var(--space-5) var(--space-6)',
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-1)' }}>
              <h1 style={{ fontSize: '1.4rem', fontWeight: 800, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {data.token_name || "Unknown Token"}
              </h1>
              {data.token_symbol && (
                <span className="badge badge-info">{data.token_symbol}</span>
              )}
            </div>
            <p className="mono text-muted" style={{ fontSize: '0.7rem', wordBreak: 'break-all' }}>
              {data.token_address}
            </p>
          </div>
          <button
            id="new-scan-btn"
            className="btn btn-ghost"
            onClick={() => navigate("/")}
            style={{ fontSize: '0.8rem', padding: '8px 16px', flexShrink: 0, marginLeft: 'var(--space-4)' }}
          >
            ← New Scan
          </button>
        </div>

        {/* ── Report Body ──────────────────────────────────── */}
        <div className="stagger" style={{
          display: 'flex', flexDirection: 'column', gap: 'var(--space-4)',
        }}>
          <TrustScore score={data.trust_score} band={data.score_band} />
          <TheCatch text={data.the_catch} />
          <TheVerdict text={data.verdict} />

          {/* Section divider */}
          <div style={{ padding: 'var(--space-2) 0' }}>
            <div className="section-divider" />
            <p style={{
              textAlign: 'center', fontSize: '0.6rem', fontWeight: 700,
              color: 'var(--text-disabled)', textTransform: 'uppercase',
              letterSpacing: '0.15em', marginTop: 'var(--space-3)',
            }}>
              Detailed Analysis
            </p>
          </div>

          <Module1Control data={data.module1} explanations={data.flag_explanations} />

          <div className="section-divider" />

          <Module2Traps data={data.module2} explanations={data.flag_explanations} />

          <div className="section-divider" />

          <Module3Collapse data={data.module3} explanations={data.flag_explanations} />
        </div>

        {/* ── Footer ───────────────────────────────────────── */}
        <div style={{
          textAlign: 'center',
          marginTop: 'var(--space-12)',
          padding: 'var(--space-6) 0',
          borderTop: '1px solid var(--border-subtle)',
        }}>
          <p style={{ color: 'var(--text-disabled)', fontSize: '0.7rem' }}>
            Scanned in {data.scan_duration_seconds}s · Data read directly from Ethereum blockchain
          </p>
          <p style={{ color: 'var(--text-disabled)', fontSize: '0.6rem', marginTop: 'var(--space-2)' }}>
            Powered by <span style={{ color: 'var(--red-400)', fontWeight: 600 }}>SafeBet</span> · On-chain analysis · No data stored
          </p>
        </div>
      </div>
    </div>
  )
}
