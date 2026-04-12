import { useEffect, useRef } from "react"
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
} from 'chart.js'
import { Doughnut } from 'react-chartjs-2'
import RiskFlag from "./RiskFlag"
import { formatPercent } from "../utils/formatters"

ChartJS.register(ArcElement, Tooltip)

/* ── Simulation Terminal Component ────────────────────────── */
function SimTerminal({ data }) {
  const sim = data.simulation_status || "unavailable"
  const isBlocked = sim === "confirmed_blocked"
  const isTaxed = sim === "confiscatory_tax"
  const isSellable = sim === "sellable"
  const isUnavailable = sim === "unavailable" || sim === "no_pair_found"

  const lines = []

  if (isUnavailable) {
    lines.push({ prompt: "$", text: "safebet simulate --buy-sell", color: "" })
    lines.push({ prompt: "⚠", text: `Simulation ${sim === "no_pair_found" ? "skipped: no trading pair found" : "unavailable for this token"}`, color: "sim-terminal-warn" })
  } else {
    lines.push({ prompt: "$", text: "safebet simulate --buy-sell", color: "" })
    lines.push({ prompt: "→", text: "Injecting 0.01 ETH test buy...", color: "sim-terminal-muted" })
    lines.push({ prompt: "✓", text: "Buy transaction: OK", color: "sim-terminal-success" })
    lines.push({ prompt: "→", text: "Attempting sell of received tokens...", color: "sim-terminal-muted" })

    if (isSellable) {
      lines.push({ prompt: "✓", text: "Sell transaction: OK — tokens are sellable", color: "sim-terminal-success" })
      if (data.current_sell_tax > 0) {
        lines.push({ prompt: "ℹ", text: `Effective sell tax detected: ${data.current_sell_tax}%`, color: "sim-terminal-warn" })
      }
    } else if (isBlocked) {
      lines.push({ prompt: "✗", text: "Sell transaction: BLOCKED", color: "sim-terminal-fail" })
      lines.push({ prompt: "!", text: data.honeypot_reason || "Transaction reverted — tokens cannot be sold", color: "sim-terminal-fail" })
    } else if (isTaxed) {
      lines.push({ prompt: "⚠", text: `Sell succeeded but confiscatory tax detected`, color: "sim-terminal-warn" })
      lines.push({ prompt: "!", text: `You'd lose most of your value on sell (tax > 50%)`, color: "sim-terminal-fail" })
    }
  }

  return (
    <div className="sim-terminal">
      <div className="sim-terminal-header">
        <div className="sim-terminal-dot" style={{ background: isBlocked || isTaxed ? 'var(--red-400)' : isSellable ? 'var(--green-400)' : 'var(--yellow-400)' }} />
        <div className="sim-terminal-dot" style={{ background: 'var(--yellow-400)', opacity: 0.6 }} />
        <div className="sim-terminal-dot" style={{ background: 'var(--text-disabled)' }} />
        <span style={{ fontSize: '0.65rem', color: 'var(--text-disabled)', marginLeft: 'auto', fontFamily: 'var(--font-mono)' }}>
          honeypot_sim.sol
        </span>
      </div>
      <div className="sim-terminal-body">
        {lines.map((line, i) => (
          <div key={i} className="sim-terminal-line" style={{ animationDelay: `${i * 150}ms` }}>
            <span className="sim-terminal-prompt">{line.prompt}</span>
            <span className={line.color}>{line.text}</span>
          </div>
        ))}
        <div className="sim-terminal-line" style={{ marginTop: 'var(--space-2)' }}>
          <span className="sim-terminal-prompt">$</span>
          <span style={{ color: 'var(--text-disabled)' }}>_</span>
          <span style={{ animation: 'blink 1s step-end infinite', color: 'var(--green-400)' }}>▊</span>
        </div>
      </div>
    </div>
  )
}

/* ── Tax Gauge Component ──────────────────────────────────── */
function TaxGauge({ label, value, max, color }) {
  const percentage = Math.min((value / (max || 100)) * 100, 100)
  const radius = 30
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (percentage / 100) * circumference

  return (
    <div className="tax-gauge">
      <div className="tax-gauge-label">{label}</div>
      <div style={{ position: 'relative', width: 76, height: 76 }}>
        <svg width="76" height="76" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="38" cy="38" r={radius} fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="5" />
          <circle cx="38" cy="38" r={radius} fill="none" stroke={color} strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 1s cubic-bezier(0.16, 1, 0.3, 1)' }}
          />
        </svg>
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <span className="tax-gauge-value" style={{ color, fontSize: '1rem' }}>
            {formatPercent(value)}
          </span>
        </div>
      </div>
    </div>
  )
}

/* ── Main Module 2 Component ──────────────────────────────── */
export default function Module2Traps({ data, explanations }) {
  if (!data) return null

  const isPending = data.honeypot_confidence === "PENDING"

  /* score color */
  const m2Score = data.m2_score ?? 100
  const scoreColor = m2Score >= 80 ? 'var(--green-400)' : m2Score >= 55 ? 'var(--yellow-400)' : m2Score >= 30 ? 'var(--orange-400)' : 'var(--red-400)'

  /* Verdict */
  const verdictMap = {
    low_concern: { label: 'LOW CONCERN', color: 'var(--green-400)', bg: 'rgba(34, 197, 94, 0.08)' },
    caution: { label: 'CAUTION', color: 'var(--yellow-400)', bg: 'rgba(234, 179, 8, 0.08)' },
    danger: { label: 'DANGER', color: 'var(--orange-400)', bg: 'rgba(249, 115, 22, 0.08)' },
    critical_danger: { label: 'CRITICAL', color: 'var(--red-400)', bg: 'rgba(239, 68, 68, 0.08)' },
    inconclusive: { label: 'INCONCLUSIVE', color: 'var(--text-muted)', bg: 'rgba(107, 114, 128, 0.08)' },
  }
  const verdict = verdictMap[data.m2_verdict] || verdictMap.inconclusive

  /* Score doughnut chart */
  const doughnutData = {
    datasets: [{
      data: [m2Score, 100 - m2Score],
      backgroundColor: [scoreColor, 'rgba(255,255,255,0.04)'],
      borderWidth: 0,
      cutout: '78%',
    }],
  }
  const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { display: false }, tooltip: { enabled: false } },
  }

  /* Detailed findings from Module 2 engine */
  const detailedFindings = data.detailed_findings || []
  const severityOrder = { critical: 0, high: 1, medium: 2, low: 3, info: 4 }
  const sortedFindings = [...detailedFindings].sort((a, b) =>
    (severityOrder[a.severity] ?? 5) - (severityOrder[b.severity] ?? 5)
  )

  const severityColor = {
    critical: 'var(--red-400)',
    high: 'var(--orange-400)',
    medium: 'var(--yellow-400)',
    low: 'var(--blue-400)',
    info: 'var(--text-muted)',
  }

  /* Tax colors */
  const taxColor = (v) => v > 10 ? 'var(--red-400)' : v > 5 ? 'var(--yellow-400)' : 'var(--green-400)'

  const flags = [
    {
      label: "Honeypot",
      brief: "Simulated a buy-then-sell to test if selling is actually blocked.",
      status: isPending ? "PENDING" : data.is_honeypot ? "DANGER" : "SAFE",
      value: isPending ? "PENDING" : data.is_honeypot ? "YES" : "NO",
      explanation: explanations?.honeypot || (
        isPending ? "Honeypot simulation is pending." :
        data.is_honeypot ? data.honeypot_reason : "Sell simulation succeeded — tokens appear to be sellable."
      ),
      decisionImpact: isPending ? null : data.is_honeypot
        ? "If you can't sell, your investment is permanently locked. This is the most critical trap in crypto."
        : "The token passed the sell test. However, this only confirms the current state — owners with tax/pause powers could change it later.",
    },
    {
      label: "Sell Tax",
      brief: "Percentage taken from you on every sell transaction.",
      status: data.current_sell_tax > 10 ? "DANGER" : data.current_sell_tax > 5 ? "WARNING" : "SAFE",
      value: formatPercent(data.current_sell_tax),
      explanation: data.current_sell_tax > 0
        ? `Every time you sell, ${formatPercent(data.current_sell_tax)} of your sale is taken as a fee.`
        : "No sell tax detected currently.",
      decisionImpact: data.current_sell_tax > 10
        ? `A ${formatPercent(data.current_sell_tax)} sell tax means you need a ${formatPercent(data.current_sell_tax / (1 - data.current_sell_tax / 100) * 100 / 100 - 100 + data.current_sell_tax)} gain just to break even. This drastically limits your ability to exit profitably.`
        : data.current_sell_tax > 5
        ? `A ${formatPercent(data.current_sell_tax)} sell tax eats into your profits on every exit. Factor this into your expected returns.`
        : "Zero or minimal sell tax means clean exits. Your actual returns match the token's performance.",
    },
    {
      label: "Buy Tax",
      brief: "Percentage taken from you on every buy transaction.",
      status: data.current_buy_tax > 10 ? "DANGER" : data.current_buy_tax > 5 ? "WARNING" : "SAFE",
      value: formatPercent(data.current_buy_tax),
      explanation: data.current_buy_tax > 0
        ? `Every time you buy, ${formatPercent(data.current_buy_tax)} of your purchase is taken as a fee.`
        : "No buy tax detected currently.",
      decisionImpact: data.current_buy_tax > 10
        ? `A ${formatPercent(data.current_buy_tax)} buy tax means you start underwater from the moment you buy.`
        : "Low or zero buy tax means your full investment goes into the token.",
    },
    {
      label: "Max Possible Tax",
      brief: "The highest the owner could set taxes to in the source code.",
      status: data.max_possible_tax > 50 ? "DANGER" : data.max_possible_tax > 25 ? "WARNING" : "SAFE",
      value: formatPercent(data.max_possible_tax),
      explanation: data.tax_is_changeable
        ? `The contract allows tax to be set up to ${formatPercent(data.max_possible_tax)}. The owner could change it at any time.`
        : "Tax rates appear to be fixed in the contract code.",
      decisionImpact: data.tax_is_changeable && data.max_possible_tax > 25
        ? `Even if current tax is low, the code allows up to ${formatPercent(data.max_possible_tax)}. The owner could raise it after you buy.`
        : "Tax rates cannot be changed. What you see is what you get.",
    },
    {
      label: "Proxy Trap",
      brief: "An upgradeable contract with an active owner — the most dangerous combination.",
      status: data.proxy_trap_active ? "DANGER" : "SAFE",
      value: data.proxy_trap_active ? "ACTIVE" : "NONE",
      explanation: data.proxy_trap_active
        ? "The contract is upgradeable AND the owner is still active. They could change the contract to steal funds."
        : "No proxy trap detected.",
      decisionImpact: data.proxy_trap_active
        ? "The developer can swap the contract's logic to anything — a drain function, a block-all-sells function, anything. This is a ticking time bomb."
        : "Without a proxy trap, the contract's behavior is locked as-is.",
    },
    {
      label: "Self Destruct",
      brief: "The contract has a kill-switch function that can delete it entirely.",
      status: data.has_selfdestruct ? "DANGER" : "SAFE",
      value: data.has_selfdestruct ? "FOUND" : "NONE",
      explanation: data.has_selfdestruct
        ? "The contract contains a self-destruct function. The developer could delete the entire contract."
        : "No self-destruct function found.",
      decisionImpact: data.has_selfdestruct
        ? "If the contract self-destructs, all token balances become permanently inaccessible. Total loss guaranteed."
        : "Without self-destruct, the contract can't be deleted from the blockchain.",
    },
  ]

  return (
    <div className="card card-glow-yellow animate-fade-in-up">
      {/* ── Module Header ────────────────────────────────── */}
      <div className="card-header">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--yellow-400)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/>
          <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>Trap Detection</span>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>Module 2</span>
        {data.critical_count > 0 && (
          <span className="badge badge-danger" style={{ marginLeft: 8 }}>
            {data.critical_count} Critical
          </span>
        )}
      </div>

      {/* ── Module Description ───────────────────────────── */}
      <div className="module-description">
        Tests whether you can actually sell this token after buying it. Simulates trades, scans for hidden
        kill-switches, and evaluates tax traps that could drain your investment.
      </div>

      {/* ── Score + Verdict + Simulation ─────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 0, borderBottom: '1px solid var(--border-subtle)' }}>

        {/* Left: Score Doughnut */}
        <div style={{ padding: 'var(--space-5)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', borderRight: '1px solid var(--border-subtle)' }}>
          <p style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-3)' }}>
            Trap Score
          </p>
          <div style={{ position: 'relative', width: 100, height: 100 }}>
            <Doughnut data={doughnutData} options={doughnutOptions} />
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            }}>
              <span style={{ fontSize: '1.6rem', fontWeight: 800, color: scoreColor, fontFamily: 'var(--font-mono)' }}>
                {m2Score}
              </span>
            </div>
          </div>
          <div style={{
            marginTop: 'var(--space-3)',
            padding: '3px 12px', borderRadius: 'var(--radius-full)',
            background: verdict.bg, color: verdict.color,
            fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.08em',
          }}>
            {verdict.label}
          </div>
          {data.data_confidence && (
            <span style={{ fontSize: '0.6rem', color: 'var(--text-disabled)', marginTop: 'var(--space-2)' }}>
              Confidence: {data.data_confidence}
            </span>
          )}
        </div>

        {/* Right: Simulation Terminal */}
        <div style={{ padding: 'var(--space-4)' }}>
          <p style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-3)' }}>
            Sell Simulation
          </p>
          <SimTerminal data={data} />
        </div>
      </div>

      {/* ── Tax Gauges ───────────────────────────────────── */}
      <div className="tax-gauges" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        <TaxGauge label="Buy Tax" value={data.current_buy_tax || 0} max={100} color={taxColor(data.current_buy_tax || 0)} />
        <TaxGauge label="Sell Tax" value={data.current_sell_tax || 0} max={100} color={taxColor(data.current_sell_tax || 0)} />
        <TaxGauge label="Max Possible" value={data.max_possible_tax || 0} max={100}
          color={data.max_possible_tax > 50 ? 'var(--red-400)' : data.max_possible_tax > 25 ? 'var(--yellow-400)' : 'var(--green-400)'}
        />
      </div>

      {/* ── Detailed Engine Findings (Threat Cards) ──────── */}
      {sortedFindings.length > 0 && (
        <div style={{ padding: 'var(--space-5)', borderBottom: '1px solid var(--border-subtle)' }}>
          <p style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-3)' }}>
            Engine Findings ({sortedFindings.length})
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            {sortedFindings.map((f, i) => (
              <div key={i} className={`threat-card threat-card-${f.severity}`}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
                  <span style={{
                    fontSize: '0.6rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em',
                    color: severityColor[f.severity] || 'var(--text-muted)',
                  }}>
                    {f.severity}
                  </span>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {f.title}
                  </span>
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                  {f.what_we_saw}
                </p>
                {f.consequence && (
                  <p style={{ fontSize: '0.72rem', color: 'var(--text-disabled)', marginTop: 'var(--space-1)', fontStyle: 'italic' }}>
                    → {f.consequence}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Standard Flags ───────────────────────────────── */}
      <div className="card-body">
        {flags.map((flag, i) => (
          <RiskFlag key={i} {...flag} />
        ))}
      </div>

      {/* ── Scan metadata ────────────────────────────────── */}
      {data.m2_scan_duration_ms && (
        <div style={{ padding: 'var(--space-3) var(--space-6)', borderTop: '1px solid var(--border-subtle)' }}>
          <p style={{ fontSize: '0.6rem', color: 'var(--text-disabled)', textAlign: 'right' }}>
            Module 2 scan: {(data.m2_scan_duration_ms / 1000).toFixed(1)}s
            {data.detected_chain && ` · ${data.detected_chain}`}
            {data.dex_name && ` · ${data.dex_name}`}
          </p>
        </div>
      )}
    </div>
  )
}
