import { useEffect, useState, useRef } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { useScan } from "../hooks/useScan"

const ETH_STEPS = [
  { label: "Connecting to Ethereum node", icon: "🔗", duration: 600 },
  { label: "Reading contract storage slots", icon: "📦", duration: 1000 },
  { label: "Fetching verified source code", icon: "📄", duration: 900 },
  { label: "Scanning source for dangers", icon: "🔍", duration: 1300 },
  { label: "Checking proxy upgrade slots", icon: "🔄", duration: 800 },
  { label: "Profiling deployer wallet", icon: "👤", duration: 1100 },
  { label: "Querying market data", icon: "📊", duration: 900 },
  { label: "Computing trust score", icon: "🛡️", duration: 700 },
]

const STELLAR_STEPS = [
  { label: "Connecting to Horizon node", icon: "🔗", duration: 600 },
  { label: "Fetching issuer account data", icon: "📦", duration: 1000 },
  { label: "Analyzing account flags", icon: "🔍", duration: 900 },
  { label: "Querying issued assets", icon: "💎", duration: 1300 },
  { label: "Checking multi-sig thresholds", icon: "🛡️", duration: 900 },
  { label: "Generating risk profile", icon: "📊", duration: 1000 },
]

export default function Scanning() {
  const [params] = useSearchParams()
  const address = params.get("address")
  const chain = params.get("chain") || "ethereum"
  const amount = parseFloat(params.get("amount") || "100")
  const navigate = useNavigate()
  const { scan, scanStellar } = useScan()

  const activeSteps = chain === "stellar" ? STELLAR_STEPS : ETH_STEPS

  const [currentStep, setCurrentStep] = useState(0)
  const [completedSteps, setCompletedSteps] = useState(new Set())
  const [scanError, setScanError] = useState(null)
  const resultRef = useRef(null)
  const animationDoneRef = useRef(false)

  // Start actual scan immediately
  useEffect(() => {
    if (!address) {
      navigate("/")
      return
    }

    const scanPromise = chain === "stellar" ? scanStellar(address) : scan(address, amount)
    scanPromise.then(result => {
      if (result) {
        resultRef.current = result
        if (animationDoneRef.current) {
          navigate("/report", { state: { data: result } })
        }
      } else {
        setScanError("Scan failed — check if the backend is running on port 8000")
      }
    })
  }, [])

  // Run the progress animation
  useEffect(() => {
    let totalDelay = 0

    activeSteps.forEach((step, i) => {
      setTimeout(() => setCurrentStep(i), totalDelay)
      totalDelay += step.duration
      setTimeout(() => {
        setCompletedSteps(prev => new Set([...prev, i]))
      }, totalDelay)
    })

    setTimeout(() => {
      animationDoneRef.current = true
      if (resultRef.current) {
        navigate("/report", { state: { data: resultRef.current } })
      }
    }, totalDelay + 400)
  }, [])

  return (
    <div className="page" style={{ justifyContent: 'center', minHeight: '100vh' }}>
      <div className="container" style={{ maxWidth: '480px' }}>

        {/* Header */}
        <div style={{ marginBottom: 'var(--space-8)' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 'var(--space-3)',
            marginBottom: 'var(--space-3)',
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, var(--red-600), var(--red-700))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              animation: 'spin-slow 3s linear infinite',
            }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
            </div>
            <h2 style={{ fontSize: '1.3rem', fontWeight: 700 }}>{chain === "stellar" ? "Scanning Issuer" : "Scanning Token"}</h2>
          </div>
          <p className="mono" style={{
            color: 'var(--text-muted)', fontSize: '0.8rem',
            wordBreak: 'break-all',
          }}>{address}</p>
        </div>

        {/* Steps */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
          {activeSteps.map((step, i) => {
            const isCompleted = completedSteps.has(i)
            const isCurrent = i === currentStep && !isCompleted
            const isPending = i > currentStep

            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 'var(--space-4)',
                padding: 'var(--space-3) var(--space-4)',
                borderRadius: 'var(--radius-md)',
                background: isCurrent ? 'var(--bg-card)' : 'transparent',
                border: isCurrent ? '1px solid var(--border-subtle)' : '1px solid transparent',
                opacity: isPending ? 0.3 : 1,
                transition: 'all 0.3s ease',
              }}>
                {/* Icon */}
                <div style={{
                  width: 28, height: 28, borderRadius: 'var(--radius-sm)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '0.85rem', flexShrink: 0,
                  background: isCompleted ? 'rgba(34, 197, 94, 0.12)' : isCurrent ? 'var(--bg-hover)' : 'transparent',
                }}>
                  {isCompleted ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--green-400)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  ) : isCurrent ? (
                    <div style={{
                      width: 10, height: 10, borderRadius: '50%',
                      border: '2px solid var(--red-400)',
                      borderTopColor: 'transparent',
                      animation: 'spin-slow 1s linear infinite',
                    }} />
                  ) : (
                    <div style={{
                      width: 6, height: 6, borderRadius: '50%',
                      background: 'var(--border-default)',
                    }} />
                  )}
                </div>

                {/* Label */}
                <span style={{
                  fontSize: '0.875rem',
                  color: isCompleted ? 'var(--text-secondary)' : isCurrent ? 'var(--text-primary)' : 'var(--text-muted)',
                  fontWeight: isCurrent ? 500 : 400,
                }}>
                  {step.label}
                </span>
              </div>
            )
          })}
        </div>

        {/* Error */}
        {scanError && (
          <div style={{
            marginTop: 'var(--space-8)',
            padding: 'var(--space-4) var(--space-5)',
            background: 'rgba(239, 68, 68, 0.08)',
            border: '1px solid rgba(239, 68, 68, 0.15)',
            borderRadius: 'var(--radius-md)',
          }}>
            <p style={{ color: 'var(--red-300)', fontSize: '0.875rem', marginBottom: 'var(--space-3)' }}>
              {scanError}
            </p>
            <button
              className="btn btn-ghost"
              onClick={() => navigate("/")}
              style={{ fontSize: '0.8rem', padding: '8px 16px' }}
            >
              ← Try Again
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
