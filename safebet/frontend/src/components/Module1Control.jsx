import { useEffect, useRef } from "react"
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
} from 'chart.js'
import { Radar } from 'react-chartjs-2'
import RiskFlag from "./RiskFlag"
import { shortAddress } from "../utils/formatters"

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip)

/* ── Radar risk scoring helper ────────────────────────────── */
function riskLevel(isRisky) { return isRisky ? 90 : 15 }

export default function Module1Control({ data, explanations }) {
  if (!data) return null

  /* ── Power Grid Cards ──────────────────────────────────── */
  const powers = [
    {
      icon: "📄", label: "Source", value: data.is_open_source ? "PUBLIC" : "HIDDEN",
      status: data.is_open_source ? "safe" : "danger",
      color: data.is_open_source ? "var(--green-400)" : "var(--red-400)",
    },
    {
      icon: "🔐", label: "Ownership",
      value: data.ownership_renounced ? "RENOUNCED" : "ACTIVE",
      status: data.ownership_renounced ? "safe" : "warning",
      color: data.ownership_renounced ? "var(--green-400)" : "var(--yellow-400)",
    },
    {
      icon: "🔄", label: "Proxy",
      value: data.is_proxy ? "YES" : "NO",
      status: data.is_proxy ? (data.ownership_renounced ? "warning" : "danger") : "safe",
      color: data.is_proxy ? "var(--red-400)" : "var(--green-400)",
    },
    {
      icon: "🪙", label: "Mintable",
      value: data.is_mintable ? "YES" : "NO",
      status: data.is_mintable ? "danger" : "safe",
      color: data.is_mintable ? "var(--red-400)" : "var(--green-400)",
    },
    {
      icon: "💸", label: "Tax Edit",
      value: data.can_change_tax ? "YES" : "NO",
      status: data.can_change_tax ? "danger" : "safe",
      color: data.can_change_tax ? "var(--red-400)" : "var(--green-400)",
    },
    {
      icon: "🚫", label: "Blacklist",
      value: data.has_blacklist ? "FOUND" : "NONE",
      status: data.has_blacklist ? "danger" : "safe",
      color: data.has_blacklist ? "var(--red-400)" : "var(--green-400)",
    },
    {
      icon: "📦", label: "Max TX",
      value: data.has_max_tx_control ? "FOUND" : "NONE",
      status: data.has_max_tx_control ? "warning" : "safe",
      color: data.has_max_tx_control ? "var(--yellow-400)" : "var(--green-400)",
    },
    {
      icon: "⏸️", label: "Trading",
      value: data.has_trading_control ? "FOUND" : "NONE",
      status: data.has_trading_control ? "warning" : "safe",
      color: data.has_trading_control ? "var(--yellow-400)" : "var(--green-400)",
    },
  ]

  /* ── Radar chart data ──────────────────────────────────── */
  const radarData = {
    labels: ['Proxy', 'Minting', 'Tax Control', 'Blacklist', 'Trading', 'Ownership'],
    datasets: [{
      label: 'Risk Level',
      data: [
        riskLevel(data.is_proxy),
        riskLevel(data.is_mintable),
        riskLevel(data.can_change_tax),
        riskLevel(data.has_blacklist),
        riskLevel(data.has_trading_control || data.has_max_tx_control),
        riskLevel(!data.ownership_renounced),
      ],
      backgroundColor: 'rgba(239, 68, 68, 0.15)',
      borderColor: 'rgba(239, 68, 68, 0.6)',
      borderWidth: 2,
      pointBackgroundColor: 'rgba(239, 68, 68, 0.8)',
      pointBorderColor: '#1a1a25',
      pointBorderWidth: 2,
      pointRadius: 4,
      pointHoverRadius: 6,
    }],
  }

  const radarOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { display: false }, tooltip: { enabled: false } },
    scales: {
      r: {
        beginAtZero: true,
        max: 100,
        ticks: { display: false, stepSize: 25 },
        grid: {
          color: 'rgba(255,255,255,0.04)',
          circular: true,
        },
        angleLines: { color: 'rgba(255,255,255,0.06)' },
        pointLabels: {
          color: '#9090a8',
          font: { size: 10, family: "'Inter', sans-serif", weight: '500' },
          padding: 12,
        },
      },
    },
  }

  /* Count dangers */
  const dangerCount = powers.filter(p => p.status === "danger").length
  const warningCount = powers.filter(p => p.status === "warning").length

  /* ── Detailed Flags ────────────────────────────────────── */
  const flags = [
    {
      label: "Source Code",
      brief: "Whether the contract code is publicly readable and verifiable.",
      status: data.is_open_source ? "SAFE" : "DANGER",
      value: data.is_open_source ? "PUBLIC" : "HIDDEN",
      explanation: data.is_open_source
        ? "The contract's source code is publicly verified on Etherscan. Anyone can audit what it does."
        : "The contract's source code is not publicly visible. There's no way to verify what this contract actually does with your money.",
      decisionImpact: data.is_open_source
        ? "Transparent code means you can verify the rules. This is the baseline for trustworthy tokens."
        : "Hidden code is a dealbreaker for most informed investors. You're trusting a complete black box with your funds.",
    },
    {
      label: "Proxy / Upgradeable",
      brief: "Whether the contract can be silently upgraded to new code.",
      status: data.is_proxy
        ? (data.ownership_renounced ? "WARNING" : "DANGER")
        : "SAFE",
      value: data.is_proxy
        ? `YES${data.proxy_type ? ` (${data.proxy_type})` : ""}`
        : "NO",
      explanation: explanations?.proxy_trap || (
        data.is_proxy
          ? `This contract uses a proxy pattern — the developer can change how it works after you've invested.${data.admin_type && data.admin_type !== 'UNKNOWN' ? ` Admin is ${data.admin_type}.` : ''}`
          : "The contract is not upgradeable. The code you see today is the code that will run forever."
      ),
      decisionImpact: data.is_proxy
        ? "An upgradeable contract means today's rules can change tomorrow. The developer could swap in code that steals all funds."
        : "Immutable contracts are more trustworthy — the rules can't silently change after you invest.",
    },
    {
      label: "Ownership",
      brief: "Whether someone still has admin control over the contract.",
      status: data.ownership_renounced ? "SAFE" : "WARNING",
      value: data.ownership_renounced ? "RENOUNCED" : shortAddress(data.owner_address),
      explanation: data.ownership_renounced
        ? "Ownership has been renounced — no single wallet can call admin functions."
        : "The contract has an active owner who can call admin functions. This isn't always bad, but it means someone has control.",
      decisionImpact: data.ownership_renounced
        ? "No owner means no single point of failure. This reduces centralization risk significantly."
        : "A live owner can call privileged functions at any moment. Combined with tax or blacklist powers, this is a risk multiplier.",
    },
    {
      label: "Tax Changeable",
      brief: "Whether buy/sell fees can be modified by the owner.",
      status: data.can_change_tax ? "DANGER" : "SAFE",
      value: data.can_change_tax ? "YES" : "NO",
      explanation: explanations?.tax_flip || (
        data.can_change_tax
          ? "The source code has a function to change the buy/sell tax. The owner could raise it to trap your money."
          : "No tax-modifying function found in the source code. Tax rates appear fixed."
      ),
      decisionImpact: data.can_change_tax
        ? "Tax can be raised to 99% after you buy, trapping your funds on sell. This is the #1 rug-pull technique."
        : "Fixed taxes give you certainty about your exit costs. This removes a major attack vector.",
    },
    {
      label: "Mintable",
      brief: "Whether new tokens can be created from nothing, diluting value.",
      status: data.is_mintable ? "DANGER" : "SAFE",
      value: data.is_mintable ? "YES" : "NO",
      explanation: explanations?.mintable || (
        data.is_mintable
          ? "The developer can create new tokens out of thin air, diluting the value of yours."
          : "No minting function found. The total supply appears to be fixed."
      ),
      decisionImpact: data.is_mintable
        ? "Minting dilutes your holdings. If someone mints 1 billion new tokens, your share becomes nearly worthless."
        : "Fixed supply means your percentage of the total cannot be diluted by someone creating more tokens.",
    },
    {
      label: "Blacklist Function",
      brief: "Whether specific wallets can be individually frozen or blocked.",
      status: data.has_blacklist ? "DANGER" : "SAFE",
      value: data.has_blacklist ? "FOUND" : "NONE",
      explanation: explanations?.blacklist || (
        data.has_blacklist
          ? "The contract can freeze specific wallets, preventing them from selling."
          : "No blacklist function found. All wallets can trade freely."
      ),
      decisionImpact: data.has_blacklist
        ? "Your specific wallet could be blacklisted, permanently locking your tokens. You'd have no recourse."
        : "Without a blacklist, your ability to trade can never be selectively revoked.",
    },
    {
      label: "Max TX Control",
      brief: "Whether the maximum transaction size can be changed.",
      status: data.has_max_tx_control ? "WARNING" : "SAFE",
      value: data.has_max_tx_control ? "FOUND" : "NONE",
      explanation: data.has_max_tx_control
        ? "The owner can change the maximum transaction size. Setting it to zero would block all trades."
        : "No max transaction control found. Trade sizes are unrestricted.",
      decisionImpact: data.has_max_tx_control
        ? "Setting max TX to near-zero blocks all trades. Even if selling isn't 'disabled,' you'd be limited to dust amounts."
        : "Unrestricted trade sizes mean you can always exit your full position in one transaction.",
    },
    {
      label: "Trading Control",
      brief: "Whether trading can be toggled on/off by the owner.",
      status: data.has_trading_control ? "WARNING" : "SAFE",
      value: data.has_trading_control ? "FOUND" : "NONE",
      explanation: data.has_trading_control
        ? "The owner can enable or disable trading entirely. They could block all sales with one transaction."
        : "No trading toggle found. Trading cannot be disabled by the owner.",
      decisionImpact: data.has_trading_control
        ? "One transaction from the owner can disable all selling globally. Your liquidity vanishes instantly."
        : "Without a trading kill-switch, the market stays open regardless of the owner's actions.",
    },
  ]

  const deployerFlags = data.deployer_address ? [
    {
      label: "Deployer History",
      brief: "Track record of the wallet that created this contract.",
      status: data.deployer_dead_ratio > 0.5 ? "DANGER" : data.deployer_dead_ratio > 0.3 ? "WARNING" : "INFO",
      value: shortAddress(data.deployer_address),
      explanation: explanations?.deployer_risk || (
        data.deployer_total_tokens > 0
          ? `This wallet has deployed ${data.deployer_total_tokens} contracts. ${data.deployer_dead_tokens} of them (${Math.round(data.deployer_dead_ratio * 100)}%) are now dead.`
          : "No deployer history data available."
      ),
      decisionImpact: data.deployer_dead_ratio > 0.5
        ? "Serial deployers with high death ratios are the hallmark of rug-pull operations. Extreme caution required."
        : data.deployer_dead_ratio > 0.3
        ? "A moderate death ratio suggests some abandoned projects. Not a clear signal alone, but worth noting."
        : "Deployer history looks normal. This alone doesn't guarantee safety, but it's a positive signal.",
    },
  ] : []

  /* Professional architecture details */
  const archDetails = []
  if (data.has_timelock_pattern) archDetails.push(`⏱️ Timelock (${data.timelock_delay_hours}h delay)`)
  if (data.has_multisig_pattern) archDetails.push("🔑 Multi-Signature")
  if (data.uses_openzeppelin) archDetails.push("🛡️ OpenZeppelin")
  if (data.has_role_based_access) archDetails.push("👥 Role-Based Access")
  if (data.has_governance) archDetails.push("🏛️ Governance")

  return (
    <div className="card card-glow-red animate-fade-in-up">
      {/* ── Module Header ────────────────────────────────── */}
      <div className="card-header">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--red-400)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
        <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>Contract Control</span>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>Module 1</span>
        {dangerCount > 0 && (
          <span className="badge badge-danger" style={{ marginLeft: 8 }}>
            {dangerCount} Risk{dangerCount > 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* ── Module Description ───────────────────────────── */}
      <div className="module-description">
        Analyzes who controls this token contract and what powers they hold. Every function below represents
        a capability that could be used against you — or a safeguard that protects your investment.
      </div>

      {/* ── Power Grid + Radar ───────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0, borderBottom: '1px solid var(--border-subtle)' }}>

        {/* Left: Power Grid */}
        <div style={{ padding: 'var(--space-4)', borderRight: '1px solid var(--border-subtle)' }}>
          <p style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-3)', paddingLeft: 'var(--space-2)' }}>
            Power Overview
          </p>
          <div className="power-grid" style={{ padding: 0 }}>
            {powers.map((p, i) => (
              <div key={i} className={`power-card power-card-${p.status}`}>
                <div className="power-card-icon">{p.icon}</div>
                <div className="power-card-label">{p.label}</div>
                <div className="power-card-value" style={{ color: p.color }}>{p.value}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Radar Chart */}
        <div style={{ padding: 'var(--space-4)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <p style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-3)' }}>
            Risk Radar
          </p>
          <div style={{ width: '100%', maxWidth: 260 }}>
            <Radar data={radarData} options={radarOptions} />
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-4)', marginTop: 'var(--space-3)' }}>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
              <span style={{ color: 'var(--green-400)' }}>●</span> Low
            </span>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
              <span style={{ color: 'var(--red-400)' }}>●</span> High
            </span>
          </div>
        </div>
      </div>

      {/* ── Professional Architecture (if any) ───────────── */}
      {archDetails.length > 0 && (
        <div style={{
          padding: 'var(--space-4) var(--space-6)',
          borderBottom: '1px solid var(--border-subtle)',
          background: 'rgba(34, 197, 94, 0.03)',
        }}>
          <p style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--green-400)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-2)' }}>
            Professional Safeguards Detected
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
            {archDetails.map((d, i) => (
              <span key={i} style={{
                padding: '4px 10px',
                background: 'rgba(34, 197, 94, 0.08)',
                border: '1px solid rgba(34, 197, 94, 0.15)',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.72rem',
                color: 'var(--green-400)',
                fontWeight: 500,
              }}>
                {d}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Detailed Flags ───────────────────────────────── */}
      <div className="card-body">
        {flags.map((flag, i) => (
          <RiskFlag key={i} {...flag} />
        ))}
        {deployerFlags.map((flag, i) => (
          <RiskFlag key={`d-${i}`} {...flag} />
        ))}
      </div>
    </div>
  )
}
