/**
 * Solr API Client für Facetten-Queries
 */

const SOLR_BASE = '/solr/nyc-taxi-raw'

/**
 * Holt Facetten und Gesamtanzahl aus Solr
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
    'facet.limit': 20,
    'facet.mincount': 1
  })

  // Facetten-Felder hinzufügen
  facetFields.forEach(field => {
    params.append('facet.field', field)
  })

  // Filter hinzufügen
  filters.forEach(fq => {
    params.append('fq', fq)
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
  // Filter als Query bauen
  const q = filters.length > 0 
    ? filters.map(f => `(${f})`).join(' AND ')
    : '*:*'

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

  filters.forEach(fq => {
    params.append('fq', fq)
  })

  const response = await fetch(`${SOLR_BASE}/select?${params}`)
  const data = await response.json()

  const buckets = data.facets?.fare_buckets?.buckets || []
  return buckets.map(b => ({
    label: `$${b.val}-${b.val + 10}`,
    count: b.count
  }))
}
