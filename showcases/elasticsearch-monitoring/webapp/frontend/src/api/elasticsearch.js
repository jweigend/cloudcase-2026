/**
 * Elasticsearch API Client fuer Monitoring-Queries
 * Alle Queries laufen ueber das Flask-Backend (kein direkter ES-Zugriff)
 */

const BACKEND_BASE = '/api'

/**
 * Konvertiert activeFilters Array zu Filter-Objekt fuer Backend
 * @param {string[]} activeFilters - Array von "field:value" Strings
 * @returns {Object} Filter-Objekt fuer Backend
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
 * Holt Facetten und Gesamtanzahl via Backend
 */
export async function fetchFacets(filters = [], facetFields = []) {
  const response = await fetch(`${BACKEND_BASE}/facets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filters: filtersToObject(filters),
      facet_fields: facetFields
    })
  })

  if (!response.ok) {
    throw new Error(`Backend error: ${response.status}`)
  }

  return await response.json()
}

/**
 * Holt Statistiken fuer Balkendiagramme
 */
export async function fetchStats(filters = [], groupBy = 'event_hour') {
  const response = await fetch(`${BACKEND_BASE}/stats`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filters: filtersToObject(filters),
      group_by: groupBy
    })
  })

  if (!response.ok) {
    throw new Error(`Backend error: ${response.status}`)
  }

  return await response.json()
}

/**
 * Holt Response-Time-Verteilung
 */
export async function fetchResponseDistribution(filters = []) {
  const response = await fetch(`${BACKEND_BASE}/response-distribution`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filters: filtersToObject(filters)
    })
  })

  if (!response.ok) {
    throw new Error(`Backend error: ${response.status}`)
  }

  return await response.json()
}

/**
 * Volltext-Suche
 */
export async function searchEvents(filters = [], query = '', size = 20) {
  const response = await fetch(`${BACKEND_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filters: filtersToObject(filters),
      query,
      size
    })
  })

  if (!response.ok) {
    throw new Error(`Backend error: ${response.status}`)
  }

  return await response.json()
}

/**
 * Health Check
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
