import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"

/* Subtle animated particles for the background */
function FloatingParticles() {
  return (
    <div style={{
      position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0, overflow: 'hidden',
    }}>
      {[...Array(20)].map((_, i) => (
        <div key={i} style={{
          position: 'absolute',
          width: `${2 + Math.random() * 3}px`,
          height: `${2 + Math.random() * 3}px`,
          background: `rgba(239, 68, 68, ${0.05 + Math.random() * 0.1})`,
          borderRadius: '50%',
          left: `${Math.random() * 100}%`,
          top: `${Math.random() * 100}%`,
          animation: `float-particle ${8 + Math.random() * 12}s ease-in-out infinite`,
          animationDelay: `${Math.random() * 5}s`,
        }} />
      ))}
      <style>{`
        @keyframes float-particle {
          0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.3; }
          25% { transform: translate(${Math.random() * 40 - 20}px, -30px) scale(1.5); opacity: 0.6; }
          50% { transform: translate(${Math.random() * 40 - 20}px, -60px) scale(1); opacity: 0.4; }
          75% { transform: translate(${Math.random() * 40 - 20}px, -30px) scale(1.3); opacity: 0.5; }
        }
      `}</style>
    </div>
  )
}

const CHAINS = [
  { id: "ethereum", label: "Ethereum", icon: "⟠", placeholder: "0x...", color: "var(--blue-400)" },
  { id: "stellar", label: "Stellar", icon: "✦", placeholder: "G...", color: "#6366f1" },
]

export default function Landing() {
  const [chain, setChain] = useState("ethereum")
  const [address, setAddress] = useState("")
  const [amount, setAmount] = useState("100")
  const [error, setError] = useState("")
  const [mounted, setMounted] = useState(false)
  const navigate = useNavigate()

  useEffect(() => { setMounted(true) }, [])

  const selectedChain = CHAINS.find(c => c.id === chain)

  const isValidEth = /^0x[a-fA-F0-9]{40}$/.test(address.trim())
  const isValidStellar = /^G[A-Z2-7]{55}$/.test(address.trim())
  const isValid = chain === "ethereum" ? isValidEth : isValidStellar

  function handleScan() {
    if (!isValid) {
      if (chain === "ethereum") {
        setError("Enter a valid Ethereum contract address (starts with 0x, 42 characters)")
      } else {
        setError("Enter a valid Stellar issuer address (starts with G, 56 characters)")
      }
      return
    }

    if (chain === "stellar") {
      navigate(`/scanning?chain=stellar&address=${address.trim()}`)
    } else {
      navigate(`/scanning?chain=ethereum&address=${address.trim()}&amount=${amount}`)
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter") handleScan()
  }

  function switchChain(newChain) {
    setChain(newChain)
    setAddress("")
    setError("")
  }

  return (
    <div className="page" style={{ justifyContent: 'center', minHeight: '100vh' }}>
      <FloatingParticles />

      <div className="container" style={{
        maxWidth: '520px',
        opacity: mounted ? 1 : 0,
        transform: mounted ? 'translateY(0)' : 'translateY(20px)',
        transition: 'all 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
      }}>

        {/* ── Logo ─────────────────────────────────────────── */}
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-16)' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            width: 64, height: 64, borderRadius: 'var(--radius-xl)',
            background: 'linear-gradient(135deg, var(--red-600), var(--red-700))',
            boxShadow: 'var(--shadow-glow-red)',
            marginBottom: 'var(--space-6)',
          }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
          </div>

          <h1 style={{
            fontSize: '3.5rem',
            fontWeight: 900,
            letterSpacing: '-0.03em',
            lineHeight: 1,
            background: 'linear-gradient(135deg, var(--text-primary) 0%, var(--text-secondary) 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>
            SAFEBET
          </h1>

          <p style={{
            color: 'var(--text-muted)',
            fontSize: '1.05rem',
            marginTop: 'var(--space-3)',
            lineHeight: 1.5,
          }}>
            Know exactly how you'd lose your money<br />
            <span style={{ color: 'var(--red-400)', fontWeight: 500 }}>before</span> you invest
          </p>
        </div>

        {/* ── Chain Selector ────────────────────────────────── */}
        <div style={{
          display: 'flex', gap: 'var(--space-2)',
          marginBottom: 'var(--space-5)',
          background: 'var(--bg-surface)',
          padding: 4,
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)',
        }}>
          {CHAINS.map(c => (
            <button
              key={c.id}
              onClick={() => switchChain(c.id)}
              style={{
                flex: 1,
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                padding: '10px 16px',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                cursor: 'pointer',
                fontSize: '0.85rem',
                fontWeight: chain === c.id ? 600 : 400,
                fontFamily: 'var(--font-sans)',
                background: chain === c.id ? 'var(--bg-card)' : 'transparent',
                color: chain === c.id ? 'var(--text-primary)' : 'var(--text-muted)',
                boxShadow: chain === c.id ? 'var(--shadow-sm)' : 'none',
                transition: 'all 150ms ease',
              }}
            >
              <span style={{ fontSize: '1rem' }}>{c.icon}</span>
              {c.label}
            </button>
          ))}
        </div>

        {/* ── Form ─────────────────────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>

          {/* Address input */}
          <div>
            <label className="input-label" htmlFor="token-address">
              {chain === "stellar" ? "Stellar Issuer Address" : "Token Contract Address"}
            </label>
            <input
              id="token-address"
              type="text"
              className="input"
              value={address}
              onChange={e => { setAddress(e.target.value); setError("") }}
              onKeyDown={handleKeyDown}
              placeholder={selectedChain.placeholder}
              spellCheck={false}
              autoComplete="off"
              style={{ fontSize: '0.9rem' }}
            />
          </div>

          {/* Investment amount — only for Ethereum */}
          {chain === "ethereum" && (
            <div>
              <label className="input-label" htmlFor="investment-amount">
                Your Investment Amount
                <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0, marginLeft: 6, opacity: 0.6 }}>
                  (for calculations)
                </span>
              </label>
              <div style={{ position: 'relative' }}>
                <span style={{
                  position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)',
                  color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.875rem',
                }}>$</span>
                <input
                  id="investment-amount"
                  type="number"
                  className="input"
                  value={amount}
                  onChange={e => setAmount(e.target.value)}
                  onKeyDown={handleKeyDown}
                  style={{ paddingLeft: 32, fontFamily: 'var(--font-sans)' }}
                />
              </div>
            </div>
          )}

          {/* Stellar info hint */}
          {chain === "stellar" && (
            <div style={{
              padding: 'var(--space-3) var(--space-4)',
              background: 'rgba(99, 102, 241, 0.06)',
              border: '1px solid rgba(99, 102, 241, 0.12)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.8rem',
              color: 'var(--text-muted)',
              lineHeight: 1.5,
            }}>
              <span style={{ color: '#818cf8', fontWeight: 500 }}>✦ Stellar Scan</span> — checks the issuer's
              account for <strong style={{ color: 'var(--text-secondary)' }}>auth_required</strong>,{' '}
              <strong style={{ color: 'var(--text-secondary)' }}>auth_revocable</strong>, and{' '}
              <strong style={{ color: 'var(--text-secondary)' }}>auth_immutable</strong> flags
              directly from the Horizon network.
            </div>
          )}

          {/* Error */}
          {error && (
            <div style={{
              padding: 'var(--space-3) var(--space-4)',
              background: 'rgba(239, 68, 68, 0.08)',
              border: '1px solid rgba(239, 68, 68, 0.15)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--red-300)',
              fontSize: '0.85rem',
            }}>
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            id="scan-button"
            className="btn btn-primary"
            onClick={handleScan}
            style={{ width: '100%', padding: '16px', fontSize: '1.05rem', marginTop: 'var(--space-2)' }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            {chain === "stellar" ? "Scan Issuer" : "Scan Token"}
          </button>
        </div>

        {/* ── Footer ───────────────────────────────────────── */}
        <p style={{
          textAlign: 'center',
          color: 'var(--text-disabled)',
          fontSize: '0.75rem',
          marginTop: 'var(--space-10)',
          lineHeight: 1.6,
        }}>
          Reads directly from {chain === "stellar" ? "Stellar Horizon" : "the Ethereum blockchain"} · No data is stored<br />
          Powered by {chain === "stellar" ? "Stellar SDK & Horizon API" : "Web3.py, Etherscan, DexScreener & Claude"}
        </p>
      </div>
    </div>
  )
}
