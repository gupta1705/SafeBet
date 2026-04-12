import { useState, useCallback } from "react"

const API_BASE = "http://localhost:8000/api"

export function useScan() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const scan = useCallback(async (address, investmentAmount = 100) => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          address: address.trim(),
          investment_amount: parseFloat(investmentAmount) || 100,
        }),
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Scan failed" }))
        throw new Error(err.detail || `Server error: ${response.status}`)
      }

      const result = await response.json()
      setData(result)
      return result
    } catch (e) {
      setError(e.message)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const scanStellar = useCallback(async (issuerAddress) => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/stellar/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          issuer_address: issuerAddress.trim(),
        }),
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Stellar scan failed" }))
        throw new Error(err.detail || `Server error: ${response.status}`)
      }

      const result = await response.json()
      setData(result)
      return result
    } catch (e) {
      setError(e.message)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setData(null)
    setError(null)
    setLoading(false)
  }, [])

  return { scan, scanStellar, data, loading, error, reset }
}
