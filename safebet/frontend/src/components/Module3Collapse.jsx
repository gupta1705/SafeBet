import {
  Chart as ChartJS,
  ArcElement,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from 'chart.js'
import { Doughnut, Bar } from 'react-chartjs-2'
import RiskFlag from "./RiskFlag"
import { formatUSD, shortAddress, formatPercent } from "../utils/formatters"

ChartJS.register(ArcElement, CategoryScale, LinearScale, BarElement, Tooltip, Legend)

/* ── LP Lock Visual ──────────────────────────────────────── */
function LPLockVisual({ data }) {
  const secured = data.lp_total_secured_percent || 0
  const burned = data.lp_burned_percent || 0
  const locked = data.lp_locked_percent || 0
  const isSecured = secured > 0

  const radius = 34
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (Math.min(secured, 100) / 100) * circumference

  const lockColor = secured >= 80 ? 'var(--green-400)' : secured >= 30 ? 'var(--yellow-400)' : 'var(--red-400)'

  return (
    <div className="lp-lock-visual">
      <p style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        LP Security
      </p>
      <div style={{ position: 'relative', width: 84, height: 84 }}>
        <svg width="84" height="84" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="42" cy="42" r={radius} fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="5" />
          <circle cx="42" cy="42" r={radius} fill="none" stroke={lockColor} strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 1s cubic-bezier(0.16, 1, 0.3, 1)' }}
          />
        </svg>
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '1.3rem',
        }}>
          {isSecured ? '🔒' : '🔓'}
        </div>
      </div>
      <div style={{ textAlign: 'center' }}>
        <span style={{ fontSize: '1rem', fontWeight: 800, color: lockColor, fontFamily: 'var(--font-mono)' }}>
          {secured.toFixed(1)}%
        </span>
        <span style={{ fontSize: '0.65rem', color: 'var(--text-disabled)', display: 'block' }}>Secured</span>
      </div>
      <div style={{ display: 'flex', gap: 'var(--space-3)', fontSize: '0.65rem', color: 'var(--text-muted)' }}>
        {burned > 0 && <span>🔥 {burned.toFixed(1)}% burned</span>}
        {locked > 0 && <span>🔒 {locked.toFixed(1)}% locked</span>}
      </div>
      {data.lp_locker_name && (
        <span style={{ fontSize: '0.6rem', color: 'var(--text-disabled)' }}>via {data.lp_locker_name}</span>
      )}
    </div>
  )
}

/* ── Liquidity Depth Meter ───────────────────────────────── */
function LiquidityMeter({ usd }) {
  // thresholds: $10K → danger, $50K → moderate, $100K+ → good
  const pct = Math.min((usd / 100000) * 100, 100)
  const color = usd < 10000 ? 'var(--red-400)' : usd < 50000 ? 'var(--yellow-400)' : 'var(--green-400)'

  return (
    <div style={{ padding: 'var(--space-4)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Liquidity Depth</span>
        <span style={{ fontSize: '0.85rem', fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>
          {formatUSD(usd)}
        </span>
      </div>
      <div style={{
        height: 8, background: 'rgba(255,255,255,0.04)', borderRadius: 'var(--radius-full)',
        overflow: 'hidden', position: 'relative',
      }}>
        <div style={{
          height: '100%', width: `${pct}%`,
          background: `linear-gradient(90deg, ${color}, ${color}88)`,
          borderRadius: 'var(--radius-full)',
          transition: 'width 1.2s cubic-bezier(0.16, 1, 0.3, 1)',
        }} />
        {/* Threshold markers */}
        <div style={{
          position: 'absolute', left: '10%', top: 0, bottom: 0, width: 1,
          background: 'rgba(255,255,255,0.1)',
        }} />
        <div style={{
          position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1,
          background: 'rgba(255,255,255,0.1)',
        }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        <span style={{ fontSize: '0.55rem', color: 'var(--text-disabled)' }}>$0</span>
        <span style={{ fontSize: '0.55rem', color: 'var(--red-400)', opacity: 0.6 }}>$10K</span>
        <span style={{ fontSize: '0.55rem', color: 'var(--yellow-400)', opacity: 0.6 }}>$50K</span>
        <span style={{ fontSize: '0.55rem', color: 'var(--green-400)', opacity: 0.6 }}>$100K+</span>
      </div>
    </div>
  )
}


export default function Module3Collapse({ data, explanations }) {
  if (!data) return null

  const hasData = data.data_status === "OK" || data.liquidity_usd > 0
  const hasLpVerification = data.lp_lock_method && data.lp_lock_method !== "unknown"

  /* ── Holder Distribution Doughnut ──────────────────────── */
  const topHolderPct = data.top_holder_percent || 0
  const top5Pct = data.top_5_holder_percent || 0
  const otherTop5 = Math.max(0, top5Pct - topHolderPct)
  const restPct = Math.max(0, 100 - top5Pct)

  const holderDoughnutData = {
    labels: ['Top Holder', 'Top 2-5', 'Rest of Holders'],
    datasets: [{
      data: [topHolderPct, otherTop5, restPct],
      backgroundColor: [
        'rgba(239, 68, 68, 0.8)',
        'rgba(249, 115, 22, 0.6)',
        'rgba(34, 197, 94, 0.3)',
      ],
      borderColor: [
        'rgba(239, 68, 68, 1)',
        'rgba(249, 115, 22, 0.8)',
        'rgba(34, 197, 94, 0.5)',
      ],
      borderWidth: 1,
      cutout: '65%',
    }],
  }
  const holderDoughnutOpts = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1a1a25',
        titleColor: '#f0f0f5',
        bodyColor: '#9090a8',
        borderColor: '#2a2a3a',
        borderWidth: 1,
        callbacks: {
          label: ctx => `${ctx.label}: ${ctx.raw.toFixed(1)}%`,
        },
      },
    },
  }

  /* ── Cascade Waterfall Bar Chart ────────────────────────── */
  const cascadeData = data.cumulative_dump_impact_percent > 0 ? {
    labels: ['Before', 'After Top 1', 'After Top 5'],
    datasets: [{
      label: 'Investment Value',
      data: [
        100,
        Math.max(0, 100 - (data.dump_price_impact_percent || 0)),
        Math.max(0, 100 - (data.cumulative_dump_impact_percent || 0)),
      ],
      backgroundColor: [
        'rgba(34, 197, 94, 0.6)',
        data.dump_price_impact_percent > 50 ? 'rgba(239, 68, 68, 0.5)' : 'rgba(249, 115, 22, 0.5)',
        data.cumulative_dump_impact_percent > 70 ? 'rgba(239, 68, 68, 0.7)' : 'rgba(249, 115, 22, 0.6)',
      ],
      borderColor: [
        'rgba(34, 197, 94, 0.8)',
        data.dump_price_impact_percent > 50 ? 'rgba(239, 68, 68, 0.8)' : 'rgba(249, 115, 22, 0.8)',
        data.cumulative_dump_impact_percent > 70 ? 'rgba(239, 68, 68, 0.9)' : 'rgba(249, 115, 22, 0.8)',
      ],
      borderWidth: 1,
      borderRadius: 4,
    }],
  } : null

  const cascadeOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1a1a25',
        titleColor: '#f0f0f5',
        bodyColor: '#9090a8',
        borderColor: '#2a2a3a',
        borderWidth: 1,
        callbacks: {
          label: ctx => `$${ctx.raw.toFixed(2)} remaining`,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: '#5a5a72', font: { size: 10, family: "'Inter', sans-serif" } },
      },
      y: {
        beginAtZero: true,
        max: 110,
        grid: { color: 'rgba(255,255,255,0.03)' },
        ticks: {
          color: '#5a5a72',
          font: { size: 10, family: "'JetBrains Mono', monospace" },
          callback: v => `$${v}`,
        },
      },
    },
  }

  const flags = [
    {
      label: "Liquidity",
      brief: "Total USD value of the trading pool that enables buying and selling.",
      status: !hasData ? "PENDING" : data.liquidity_usd < 10000 ? "DANGER" : data.liquidity_usd < 50000 ? "WARNING" : "SAFE",
      value: hasData ? formatUSD(data.liquidity_usd) : "NO DATA",
      explanation: explanations?.liquidity_risk || (
        !hasData ? "No liquidity pool found on DEX." :
        data.liquidity_usd < 10000 ? "Very low liquidity — even small trades can cause wild price swings." :
        data.liquidity_usd < 50000 ? "Moderate liquidity — large trades may move the price significantly." :
        "Healthy liquidity depth — the pool can absorb reasonable trade volumes."
      ),
      decisionImpact: !hasData
        ? "Without a trading pool, you cannot buy or sell this token on a DEX."
        : data.liquidity_usd < 10000
        ? "With less than $10K in liquidity, a $100 trade could move the price by 1% or more. Slippage will eat your profits."
        : data.liquidity_usd < 50000
        ? "Moderate liquidity means careful trade sizing is needed. Large sells will cause noticeable slippage."
        : "Deep liquidity means your trades have minimal price impact. You can enter and exit positions cleanly.",
    },
    {
      label: "Liquidity Lock",
      brief: "Whether the developer can drain the trading pool funds.",
      status: !hasData ? "PENDING" : data.liquidity_locked ? "SAFE" : "DANGER",
      value: !hasData ? "NO DATA" : data.liquidity_locked ? "LOCKED" : "UNLOCKED",
      explanation: !data.liquidity_locked && hasData
        ? "The trading pool funds are not locked. The developer can drain them at any time, taking everyone's money."
        : hasLpVerification ? data.lp_consequence : (data.liquidity_locked ? "Liquidity pool tokens are locked — the developer cannot drain the pool." : null),
      decisionImpact: !data.liquidity_locked && hasData
        ? "Unlocked liquidity is the classic rug-pull setup. The developer can remove all pool funds in one transaction, crashing the price to zero."
        : "Locked liquidity protects against the most basic rug-pull. The developer physically cannot drain trading pool funds.",
    },
    ...(hasLpVerification ? [{
      label: "LP Verification",
      brief: "On-chain verification of LP token lock status (burned or locked in contract).",
      status: data.lp_total_secured_percent >= 80 ? "SAFE" : data.lp_total_secured_percent >= 30 ? "WARNING" : "DANGER",
      value: data.lp_lock_method === "burned"
        ? `🔥 ${data.lp_burned_percent.toFixed(1)}% Burned`
        : data.lp_locker_name
          ? `🔒 ${data.lp_locker_name}`
          : `${data.lp_total_secured_percent.toFixed(1)}% Secured`,
      explanation: data.lp_consequence,
      decisionImpact: data.lp_total_secured_percent >= 80
        ? "Over 80% of LP tokens are secured. This is a strong protection against liquidity pulls."
        : `Only ${data.lp_total_secured_percent.toFixed(1)}% is secured. The remaining LP tokens could be withdrawn.`,
    }] : []),
    {
      label: "Top Holder",
      brief: "The largest single wallet's share of total token supply.",
      status: data.top_holder_percent > 30 ? "DANGER" : data.top_holder_percent > 15 ? "WARNING" : data.top_holder_percent > 0 ? "SAFE" : "PENDING",
      value: data.top_holder_percent > 0
        ? `${formatPercent(data.top_holder_percent)}${data.top_holder_address ? ` (${shortAddress(data.top_holder_address)})` : ''}`
        : "NO DATA",
      explanation: data.top_holder_percent > 15
        ? `One wallet controls ${formatPercent(data.top_holder_percent)} of all tokens. If they sell, the price crashes.`
        : data.top_holder_percent > 0
        ? `The top holder owns ${formatPercent(data.top_holder_percent)} of supply — within a reasonable range.`
        : null,
      decisionImpact: data.top_holder_percent > 30
        ? "A single wallet controlling over 30% is extreme. Their sell would crash the price by the dump impact shown below."
        : data.top_holder_percent > 15
        ? "Moderate concentration. Factor in the dump impact percentage when sizing your position."
        : "Healthy distribution means no single wallet can crash the price catastrophically.",
    },
    ...(data.top_5_holder_percent > 0 ? [{
      label: "Top 5 Holders",
      brief: "Combined token supply held by the 5 largest wallets.",
      status: data.top_5_holder_percent > 60 ? "DANGER" : data.top_5_holder_percent > 40 ? "WARNING" : "SAFE",
      value: formatPercent(data.top_5_holder_percent),
      explanation: data.top_5_holder_percent > 40
        ? `The top 5 wallets collectively control ${formatPercent(data.top_5_holder_percent)} of all tokens.`
        : `Top 5 holders own ${formatPercent(data.top_5_holder_percent)} — a relatively distributed supply.`,
      decisionImpact: data.top_5_holder_percent > 60
        ? "Over 60% in 5 wallets means coordinated selling (or even panic selling) would be catastrophic."
        : "Reasonable distribution across top holders reduces coordinated dump risk.",
    }] : []),
    {
      label: "Dump Impact",
      brief: "Simulated price drop if the top holder sells their entire position.",
      status: data.dump_price_impact_percent > 50 ? "DANGER" : data.dump_price_impact_percent > 20 ? "WARNING" : data.dump_price_impact_percent > 0 ? "SAFE" : "PENDING",
      value: data.dump_price_impact_percent > 0 ? formatPercent(data.dump_price_impact_percent) : "NO DATA",
      explanation: explanations?.dump_risk || (
        data.dump_price_impact_percent > 0
          ? `If the top holder sells everything, the price drops ${formatPercent(data.dump_price_impact_percent)}.`
          : null
      ),
      decisionImpact: data.dump_price_impact_percent > 50
        ? `A ${formatPercent(data.dump_price_impact_percent)} crash from one wallet selling means you'd lose over half your investment instantly.`
        : data.dump_price_impact_percent > 20
        ? `A ${formatPercent(data.dump_price_impact_percent)} impact is significant. Size your position assuming this could happen at any time.`
        : "Low dump impact means even a full sell-off from the top holder would have moderate market effect.",
    },
    ...(data.cumulative_dump_impact_percent > 0 ? [{
      label: "Cascade Impact",
      brief: "Total price drop if the top 5 holders sell sequentially (panic scenario).",
      status: data.cumulative_dump_impact_percent > 70 ? "DANGER" : data.cumulative_dump_impact_percent > 40 ? "WARNING" : "SAFE",
      value: formatPercent(data.cumulative_dump_impact_percent),
      explanation: `If the top 5 holders panic sell sequentially, the total price drop would be ${formatPercent(data.cumulative_dump_impact_percent)}.`,
      decisionImpact: data.cumulative_dump_impact_percent > 70
        ? `A ${formatPercent(data.cumulative_dump_impact_percent)} cascade wipeout means near-total loss in a panic scenario.`
        : `A ${formatPercent(data.cumulative_dump_impact_percent)} cascade impact is within acceptable range for crypto's volatility.`,
    }] : []),
    {
      label: "Holder Grade",
      brief: "Overall grade for token distribution health (A=best, F=worst).",
      status: ["A", "B"].includes(data.holder_grade) ? "SAFE" : ["C"].includes(data.holder_grade) ? "WARNING" : data.holder_grade === "N/A" ? "PENDING" : "DANGER",
      value: data.holder_grade,
      explanation: data.holder_grade === "N/A" ? null :
        data.holder_grade === "A" ? "Healthy token distribution — low concentration risk." :
        data.holder_grade === "B" ? "Moderate holder concentration — some dump risk." :
        data.holder_grade === "C" ? "High concentration — significant dump risk." :
        data.holder_grade === "D" ? "Very high concentration — major dump risk." :
        "Extreme concentration — near-certain rug risk.",
      decisionImpact: data.holder_grade === "A"
        ? "Grade A distribution is ideal — no single entity can crash the market."
        : data.holder_grade === "F"
        ? "Grade F means this token is essentially controlled by a handful of wallets. Avoid or size position to zero."
        : data.holder_grade === "N/A" ? null
        : `Grade ${data.holder_grade} means you should factor concentration risk into your position sizing.`,
    },
  ]

  return (
    <div className="card card-glow-orange animate-fade-in-up">
      {/* ── Module Header ────────────────────────────────── */}
      <div className="card-header">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--orange-400)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>Market & Collapse Analysis</span>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>Module 3</span>
        {data.data_status === "NO_PAIR" && <span className="badge badge-pending" style={{ marginLeft: 8 }}>No DEX Pair</span>}
        {data.data_status === "LOW_LIQUIDITY" && <span className="badge badge-pending" style={{ marginLeft: 8 }}>Low Liquidity</span>}
      </div>

      {/* ── Module Description ───────────────────────────── */}
      <div className="module-description">
        Simulates what would happen to your investment if large holders sell. Analyzes liquidity depth,
        holder concentration, and runs a cascade sell simulation using AMM math.
      </div>

      {/* ── Liquidity Depth Meter ─────────────────────────── */}
      {hasData && (
        <div style={{ borderBottom: '1px solid var(--border-subtle)' }}>
          <LiquidityMeter usd={data.liquidity_usd || 0} />
        </div>
      )}

      {/* ── Charts Row ───────────────────────────────────── */}
      {hasData && (topHolderPct > 0 || cascadeData) && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: topHolderPct > 0 && cascadeData ? '1fr 1fr' : '1fr',
          gap: 0,
          borderBottom: '1px solid var(--border-subtle)',
        }}>
          {/* Holder Distribution Doughnut */}
          {topHolderPct > 0 && (
            <div style={{
              padding: 'var(--space-5)',
              borderRight: cascadeData ? '1px solid var(--border-subtle)' : 'none',
              display: 'flex', flexDirection: 'column', alignItems: 'center',
            }}>
              <p style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-3)' }}>
                Holder Distribution
              </p>
              <div style={{ width: '100%', maxWidth: 180 }}>
                <Doughnut data={holderDoughnutData} options={holderDoughnutOpts} />
              </div>
              <div style={{ display: 'flex', gap: 'var(--space-4)', marginTop: 'var(--space-3)', flexWrap: 'wrap', justifyContent: 'center' }}>
                <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: 'rgba(239, 68, 68, 0.8)' }} /> Top 1 ({formatPercent(topHolderPct)})
                </span>
                <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: 'rgba(249, 115, 22, 0.6)' }} /> 2-5 ({formatPercent(otherTop5)})
                </span>
                <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: 'rgba(34, 197, 94, 0.3)' }} /> Rest ({formatPercent(restPct)})
                </span>
              </div>
            </div>
          )}

          {/* Cascade Waterfall Bar Chart */}
          {cascadeData && (
            <div style={{ padding: 'var(--space-5)', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <p style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-3)' }}>
                Dump Cascade ($100 invested)
              </p>
              <div style={{ width: '100%', maxWidth: 260 }}>
                <Bar data={cascadeData} options={cascadeOptions} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── LP Lock Visual + Investment Impact ──────────── */}
      {hasData && (hasLpVerification || data.dump_price_impact_percent > 0) && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: hasLpVerification ? '160px 1fr' : '1fr',
          gap: 0,
          borderBottom: '1px solid var(--border-subtle)',
        }}>
          {hasLpVerification && (
            <div style={{ borderRight: '1px solid var(--border-subtle)' }}>
              <LPLockVisual data={data} />
            </div>
          )}

          {/* Investment Impact */}
          {data.dump_price_impact_percent > 0 && (
            <div style={{ padding: 'var(--space-5)' }}>
              <p style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-4)' }}>
                Your Investment After Dump
              </p>
              <div style={{
                display: 'grid', gridTemplateColumns: '1fr auto 1fr',
                alignItems: 'center', gap: 'var(--space-4)',
                textAlign: 'center',
              }}>
                <div>
                  <p style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Before
                  </p>
                  <p style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--green-400)', fontFamily: 'var(--font-mono)' }}>
                    {formatUSD(100)}
                  </p>
                </div>
                <div style={{
                  color: data.dump_price_impact_percent > 50 ? 'var(--red-400)' : data.dump_price_impact_percent > 20 ? 'var(--orange-400)' : 'var(--yellow-400)',
                  fontSize: '1.2rem',
                }}>→</div>
                <div>
                  <p style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    After Dump
                  </p>
                  <p style={{
                    fontSize: '1.3rem', fontWeight: 700, fontFamily: 'var(--font-mono)',
                    color: data.dump_price_impact_percent > 50 ? 'var(--red-400)' : data.dump_price_impact_percent > 20 ? 'var(--orange-400)' : 'var(--yellow-400)',
                  }}>
                    {formatUSD(data.investment_value_after_dump)}
                  </p>
                </div>
              </div>

              {/* Price Impact Bar */}
              <div style={{ marginTop: 'var(--space-4)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Price Impact</span>
                  <span style={{
                    fontSize: '0.65rem', fontWeight: 600, fontFamily: 'var(--font-mono)',
                    color: data.dump_price_impact_percent > 50 ? 'var(--red-400)' : data.dump_price_impact_percent > 20 ? 'var(--orange-400)' : 'var(--yellow-400)',
                  }}>
                    -{formatPercent(data.dump_price_impact_percent)}
                  </span>
                </div>
                <div style={{
                  height: 6, background: 'rgba(255,255,255,0.04)', borderRadius: 'var(--radius-full)',
                  overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%',
                    width: `${Math.min(data.dump_price_impact_percent, 100)}%`,
                    background: data.dump_price_impact_percent > 50 ? 'var(--red-400)' : data.dump_price_impact_percent > 20 ? 'var(--orange-400)' : 'var(--yellow-400)',
                    borderRadius: 'var(--radius-full)',
                    transition: 'width 1s cubic-bezier(0.16, 1, 0.3, 1)',
                  }} />
                </div>
              </div>

              {/* Cascade Bar */}
              {data.cumulative_dump_impact_percent > 0 && (
                <div style={{ marginTop: 'var(--space-3)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Top 5 Cascade</span>
                    <span style={{
                      fontSize: '0.65rem', fontWeight: 600, fontFamily: 'var(--font-mono)',
                      color: data.cumulative_dump_impact_percent > 70 ? 'var(--red-400)' : data.cumulative_dump_impact_percent > 40 ? 'var(--orange-400)' : 'var(--yellow-400)',
                    }}>
                      -{formatPercent(data.cumulative_dump_impact_percent)}
                    </span>
                  </div>
                  <div style={{
                    height: 6, background: 'rgba(255,255,255,0.04)', borderRadius: 'var(--radius-full)',
                    overflow: 'hidden',
                  }}>
                    <div style={{
                      height: '100%',
                      width: `${Math.min(data.cumulative_dump_impact_percent, 100)}%`,
                      background: data.cumulative_dump_impact_percent > 70 ? 'var(--red-400)' : data.cumulative_dump_impact_percent > 40 ? 'var(--orange-400)' : 'var(--yellow-400)',
                      borderRadius: 'var(--radius-full)',
                      transition: 'width 1.2s cubic-bezier(0.16, 1, 0.3, 1)',
                    }} />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Detailed Flags ───────────────────────────────── */}
      <div className="card-body">
        {flags.map((flag, i) => (
          <RiskFlag key={i} {...flag} />
        ))}
      </div>
    </div>
  )
}
