/**
 * Backend API Client für Spark-basierte Routen-Analyse
 */

const BACKEND_BASE = '/api'

/**
 * Zählt Fahrten für gegebene Filter (schnell via Solr)
 * @param {Object} filters - Filter-Objekt
 * @returns {Promise<{count: number, can_analyze: boolean}>}
 */
export async function countTrips(filters = {}) {
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
 * Berechnet Top-N lukrativste Routen via Spark
 * @param {Object} filters - Filter-Objekt
 * @param {number} limit - Anzahl der Routen (max 20)
 * @returns {Promise<{routes: Array, total_trips: number}>}
 */
export async function fetchTopRoutes(filters = {}, limit = 5) {
  const response = await fetch(`${BACKEND_BASE}/top-routes`, {
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
 * Konvertiert activeFilters Array zu Filter-Objekt für Backend
 * @param {string[]} activeFilters - Array von "field:value" Strings
 * @returns {Object} Filter-Objekt für Backend
 * 
 * Unterstützt:
 * - Einfache Filter: "payment_type:1" 
 * - Range-Filter: "total_amount:[10 TO 20]"
 */
export function filtersToObject(activeFilters) {
  const result = {}
  
  for (const fq of activeFilters) {
    // Finde ersten : der nicht Teil einer Range ist
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
      // Versuche als Zahl zu parsen
      const numValue = parseInt(value, 10)
      result[field].push(isNaN(numValue) ? value : numValue)
    }
  }
  
  return result
}

/**
 * Health Check für Backend
 * @returns {Promise<boolean>}
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
