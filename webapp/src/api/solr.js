/**
 * Solr API Client für Facetten-Queries
 */

const SOLR_BASE = '/solr/nyc-taxi-raw'

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
 * Gruppiert Filter nach Feld und verbindet sie mit OR
 * z.B. ["payment_type:1", "payment_type:2", "pickup_hour:14"]
 * -> ["(payment_type:1 OR payment_type:2)", "pickup_hour:14"]
 */
function groupFiltersByField(filters) {
  const grouped = {}
  
  filters.forEach(fq => {
    const field = getFieldFromFilter(fq)
    if (field) {
      if (!grouped[field]) {
        grouped[field] = []
      }
      grouped[field].push(fq)
    }
  })
  
  // Jede Gruppe mit OR verbinden
  return Object.entries(grouped).map(([field, fqs]) => {
    if (fqs.length === 1) {
      return { field, query: fqs[0] }
    }
    return { field, query: `(${fqs.join(' OR ')})` }
  })
}

/**
 * Holt Facetten und Gesamtanzahl aus Solr
 * Verwendet Tag/Exclude für echte Mehrfachauswahl
 * @param {string[]} filters - Array von Filter-Queries (fq)
 * @param {string[]} facetFields - Felder für Facetten
 * @returns {Promise<{numFound: number, facets: Object}>}
 */
export async function fetchFacets(filters = [], facetFields = []) {
  const params = new URLSearchParams({
    q: '*:*',
    rows: 0,
    wt: 'json',
    facet: 'true',
    'facet.limit': 30,  // Erhöht von 20 auf 30, damit alle 24 Uhrzeiten angezeigt werden
    'facet.mincount': 1
  })

  // Facetten-Felder mit Exclude-Tag hinzufügen
  // Dadurch werden die Facetten-Zählungen ohne den eigenen Filter berechnet
  facetFields.forEach(field => {
    params.append('facet.field', `{!ex=${field}}${field}`)
  })

  // Filter gruppieren (gleiches Feld = OR) und mit Tags hinzufügen
  const groupedFilters = groupFiltersByField(filters)
  groupedFilters.forEach(({ field, query }) => {
    params.append('fq', `{!tag=${field}}${query}`)
  })

  const response = await fetch(`${SOLR_BASE}/select?${params}`)
  const data = await response.json()

  // Facetten-Daten parsen (Solr gibt [value, count, value, count, ...] zurück)
  const facets = {}
  const facetFields_raw = data.facet_counts?.facet_fields || {}
  
  for (const [field, values] of Object.entries(facetFields_raw)) {
    facets[field] = []
    for (let i = 0; i < values.length; i += 2) {
      facets[field].push({
        value: values[i],
        count: values[i + 1]
      })
    }
  }

  return {
    numFound: data.response.numFound,
    facets
  }
}

/**
 * Holt Statistiken für Balkendiagramme via Streaming Expression
 * @param {string[]} filters - Array von Filter-Queries
 * @param {string} groupBy - Feld zum Gruppieren
 * @returns {Promise<Array>}
 */
export async function fetchStats(filters = [], groupBy = 'pickup_hour') {
  // Filter gruppieren (gleiches Feld = OR, verschiedene Felder = AND)
  const groupedFilters = groupFiltersByField(filters)
  
  // Query bauen und für Streaming Expression escapen
  let q = '*:*'
  if (groupedFilters.length > 0) {
    q = groupedFilters.map(({ query }) => `(${query})`).join(' AND ')
    // Escape für Streaming Expression (doppelte Anführungszeichen durch einfache ersetzen)
    q = q.replace(/"/g, '\\"')
  }

  const expr = `
    rollup(
      search(nyc-taxi-raw,
        q="${q}",
        fl="${groupBy},total_amount",
        sort="${groupBy} asc",
        qt="/export"
      ),
      over="${groupBy}",
      sum(total_amount),
      avg(total_amount),
      count(*)
    )
  `.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim()

  const params = new URLSearchParams({ expr })
  
  const response = await fetch(`${SOLR_BASE}/stream?${params}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  })
  
  const data = await response.json()
  
  // Stream-Ergebnis parsen (entferne EOF-Marker)
  const docs = data['result-set']?.docs || []
  return docs.filter(doc => !('EOF' in doc))
}

/**
 * Holt Fahrpreis-Verteilung in Buckets
 * @param {string[]} filters - Array von Filter-Queries
 * @returns {Promise<Array>}
 */
export async function fetchFareDistribution(filters = []) {
  const params = new URLSearchParams({
    q: '*:*',
    rows: 0,
    wt: 'json',
    'json.facet': JSON.stringify({
      fare_buckets: {
        type: 'range',
        field: 'total_amount',
        start: 0,
        end: 100,
        gap: 10
      }
    })
  })

  // Filter gruppieren (gleiches Feld = OR)
  const groupedFilters = groupFiltersByField(filters)
  groupedFilters.forEach(({ query }) => {
    params.append('fq', query)
  })

  const response = await fetch(`${SOLR_BASE}/select?${params}`)
  const data = await response.json()

  const buckets = data.facets?.fare_buckets?.buckets || []
  return buckets.map(b => ({
    label: `$${b.val}-${b.val + 10}`,
    count: b.count,
    val: b.val
  }))
}
