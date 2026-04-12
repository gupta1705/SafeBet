/**
 * Format a number as USD with intelligent abbreviation
 */
export const formatUSD = (amount) => {
  if (amount == null || isNaN(amount)) return "$0.00"
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(2)}M`
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(1)}K`
  return `$${amount.toFixed(2)}`
}

/**
 * Shorten an Ethereum address for display
 */
export const shortAddress = (addr) => {
  if (!addr) return "Unknown"
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`
}

/**
 * Get the CSS color for a trust score
 */
export const scoreColor = (score) => {
  if (score >= 80) return "var(--green-400)"
  if (score >= 55) return "var(--yellow-400)"
  if (score >= 30) return "var(--orange-400)"
  return "var(--red-400)"
}

/**
 * Get a CSS class for the score band text
 */
export const scoreBandClass = (band) => {
  const map = {
    "LOW RISK": "text-green",
    "MODERATE RISK": "text-yellow",
    "HIGH RISK": "text-orange",
    "CRITICAL RISK": "text-red",
  }
  return map[band] || "text-muted"
}

/**
 * Format a percentage for display
 */
export const formatPercent = (value) => {
  if (value == null || isNaN(value)) return "0%"
  return `${Number(value).toFixed(1)}%`
}

/**
 * Format a timestamp to a readable date
 */
export const formatDate = (timestamp) => {
  if (!timestamp) return "Unknown"
  const date = new Date(timestamp * 1000)
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}
