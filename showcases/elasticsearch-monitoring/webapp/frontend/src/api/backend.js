/**
 * Backend API Client fuer Alert-Analyse
 */

const BACKEND_BASE = '/api'

/**
 * Konvertiert activeFilters Array zu Filter-Objekt fuer Backend
 */
export function filtersToObject(activeFilters) {
  const result = {}

  for (const fq of activeFilters) {
    const colonIndex = fq.indexOf(':')
    if (colonIndex === -1) continue

    const field = fq.substring(0, colonIndex)
    const value = fq.substring(colonIndex + 1)

    if (!result[field]) {
      result[field] = []
    }

    if (value.startsWith('[') && value.includes(' TO ')) {
      result[field].push(value)
    } else {
      const numValue = parseInt(value, 10)
      result[field].push(isNaN(numValue) ? value : numValue)
    }
  }

  return result
}

/**
 * Zaehlt Events fuer gegebene Filter
 */
export async function countEvents(filters = {}) {
  const response = await fetch(`${BACKEND_BASE}/count`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filters })
  })

  if (!response.ok) {
    throw new Error(`Backend error: ${response.status}`)
  }

  return await response.json()
}

/**
 * Top Alerts via Elasticsearch
 */
export async function fetchTopAlerts(filters = {}, limit = 5) {
  const response = await fetch(`${BACKEND_BASE}/top-alerts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filters, limit })
  })

  if (!response.ok) {
    throw new Error(`Backend error: ${response.status}`)
  }

  return await response.json()
}

/**
 * Health Check fuer Backend
 */
export async function checkBackendHealth() {
  try {
    const response = await fetch(`${BACKEND_BASE}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(3000)
    })
    return response.ok
  } catch {
    return false
  }
}
