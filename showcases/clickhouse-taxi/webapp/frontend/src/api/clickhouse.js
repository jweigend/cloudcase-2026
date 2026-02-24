/**
 * ClickHouse API Client für Facetten-Queries
 * Alle Queries laufen über das Flask-Backend (kein direkter DB-Zugriff)
 */

const BACKEND_BASE = '/api'

/**
 * Extrahiert das Feld aus einem Filter-Query
 * z.B. "payment_type:1" -> "payment_type"
 * z.B. "total_amount:[0 TO 10]" -> "total_amount"
 */
function getFieldFromFilter(fq) {
  const colonIndex = fq.indexOf(':')
  return colonIndex > 0 ? fq.substring(0, colonIndex) : null
}

/**
 * Konvertiert activeFilters Array zu Filter-Objekt für Backend
 * @param {string[]} activeFilters - Array von "field:value" Strings
 * @returns {Object} Filter-Objekt für Backend
 */
function filtersToObject(activeFilters) {
  const result = {}

  for (const fq of activeFilters) {
    const colonIndex = fq.indexOf(':')
    if (colonIndex === -1) continue

    const field = fq.substring(0, colonIndex)
    const value = fq.substring(colonIndex + 1)

    if (!result[field]) {
      result[field] = []
    }

    // Range-Filter behalten (z.B. "[10 TO 20]")
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
 * Verwendet Exclude-Logik für echte Mehrfachauswahl
 * @param {string[]} filters - Array von Filter-Queries (fq)
 * @param {string[]} facetFields - Felder für Facetten
 * @returns {Promise<{numFound: number, facets: Object}>}
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
 * Holt Statistiken für Balkendiagramme
 * @param {string[]} filters - Array von Filter-Queries
 * @param {string} groupBy - Feld zum Gruppieren
 * @returns {Promise<Array>}
 */
export async function fetchStats(filters = [], groupBy = 'pickup_hour') {
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
 * Holt Fahrpreis-Verteilung in Buckets
 * @param {string[]} filters - Array von Filter-Queries
 * @returns {Promise<Array>}
 */
export async function fetchFareDistribution(filters = []) {
  const response = await fetch(`${BACKEND_BASE}/fare-distribution`, {
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
