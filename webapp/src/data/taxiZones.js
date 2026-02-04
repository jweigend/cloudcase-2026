// NYC Taxi Zone Lookup - lädt Daten vom Backend API
// Single Source of Truth: webapp/backend/data/taxi-zones.json
// API Endpoint: /api/zone-names

// Backend Base URL (gleiche wie in backend.js)
const BACKEND_BASE = '/api'

// Cache für geladene Zonen
let taxiZonesCache = null
let loadingPromise = null

/**
 * Lädt die Taxi Zones vom Backend (einmalig, dann gecached)
 * @returns {Promise<Object>} Zone Mappings
 */
export async function loadTaxiZones() {
  // Bereits geladen?
  if (taxiZonesCache) {
    return taxiZonesCache
  }
  
  // Bereits am Laden?
  if (loadingPromise) {
    return loadingPromise
  }
  
  // Neu laden
  loadingPromise = (async () => {
    try {
      const response = await fetch(`${BACKEND_BASE}/zone-names`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      taxiZonesCache = await response.json()
      console.log(`Loaded ${Object.keys(taxiZonesCache).length} taxi zones from backend`)
      return taxiZonesCache
    } catch (error) {
      console.error('Failed to load taxi zones from backend:', error)
      // Fallback: leeres Objekt, damit die App weiter funktioniert
      taxiZonesCache = {}
      return taxiZonesCache
    } finally {
      loadingPromise = null
    }
  })()
  
  return loadingPromise
}

/**
 * Gibt die geladenen Taxi Zones zurück (synchron, aus Cache)
 * ACHTUNG: Muss vorher mit loadTaxiZones() initialisiert werden!
 * @returns {Object} Zone Mappings oder leeres Objekt
 */
export function getTaxiZones() {
  return taxiZonesCache || {}
}

/**
 * Gibt den Namen einer NYC Taxi Zone zurück
 * @param {number|string} id - Location ID (1-265)
 * @param {boolean} includeBorough - Wenn true, wird der Borough-Kürzel angehängt
 * @returns {string} Zone Name, optional mit Borough
 */
export function getZoneName(id, includeBorough = false) {
  const zones = getTaxiZones()
  const zone = zones[String(id)]
  if (!zone) return `Zone ${id}`
  return includeBorough ? `${zone.name} (${zone.short})` : zone.name
}

/**
 * Gibt das Borough einer Zone zurück
 * @param {number|string} id - Location ID (1-265)
 * @returns {string} Borough Name
 */
export function getZoneBorough(id) {
  const zones = getTaxiZones()
  const zone = zones[String(id)]
  return zone ? zone.borough : 'Unknown'
}

/**
 * Gibt das Kürzel einer Zone zurück (MAN, BK, QN, BX, SI, EWR)
 * @param {number|string} id - Location ID (1-265)
 * @returns {string} Borough Kürzel
 */
export function getZoneShort(id) {
  const zones = getTaxiZones()
  const zone = zones[String(id)]
  return zone ? zone.short : 'N/A'
}
