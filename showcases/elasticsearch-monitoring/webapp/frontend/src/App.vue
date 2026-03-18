<template>
  <div class="h-screen flex flex-col">
    <!-- Header -->
    <header class="bg-emerald-700 text-white px-6 py-4 shadow-lg">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold">Monitoring Data Explorer</h1>
          <p class="text-emerald-200 text-sm">Cloudkoffer 2026 - Elasticsearch Showcase</p>
        </div>
        <div class="text-right">
          <div class="text-3xl font-bold">{{ formatNumber(totalDocs) }}</div>
          <div class="text-emerald-200 text-sm">Events</div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 flex overflow-hidden">
      <!-- Left Panel: Facetten -->
      <aside class="w-80 bg-white border-r border-gray-200 overflow-y-auto facet-scroll">
        <FacetPanel
          :facets="facets"
          :activeFilters="activeFilters"
          :loading="loading"
          @toggle-filter="toggleFilter"
          @clear-filters="clearFilters"
          @remove-filter="removeFilter"
        />
      </aside>

      <!-- Right Panel: Statistiken + Top Alerts -->
      <section class="flex-1 bg-gray-50 p-6 overflow-y-auto space-y-6">
        <StatsPanel
          :hourlyStats="hourlyStats"
          :responseDistribution="responseDistribution"
          :loading="loading"
          :activeFilters="activeFilters"
          @add-hour-filter="addHourFilter"
          @add-response-filter="addResponseFilter"
        />

        <!-- Top Alerts Panel -->
        <TopAlertsPanel
          :activeFilters="activeFilters"
        />
      </section>
    </main>

    <!-- Footer -->
    <footer class="bg-gray-800 text-gray-400 px-6 py-2 text-sm">
      <div class="flex justify-between">
        <span>Elasticsearch: cloudkoffer Cluster (4 Nodes)</span>
        <span>Letzte Abfrage: {{ queryTime }}ms</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import FacetPanel from './components/FacetPanel.vue'
import StatsPanel from './components/StatsPanel.vue'
import TopAlertsPanel from './components/TopAlertsPanel.vue'
import { fetchFacets, fetchStats, fetchResponseDistribution } from './api/elasticsearch.js'

// Facetten-Felder
const FACET_FIELDS = [
  'severity',
  'event_type',
  'host',
  'service',
  'status_code'
]

// State
const totalDocs = ref(0)
const facets = ref({})
const activeFilters = ref([])
const hourlyStats = ref([])
const responseDistribution = ref([])
const loading = ref(true)
const queryTime = ref(0)

// Daten laden
async function loadData() {
  loading.value = true
  const startTime = Date.now()

  try {
    const [facetResult, hourly, responses] = await Promise.all([
      fetchFacets(activeFilters.value, FACET_FIELDS),
      fetchStats(activeFilters.value, 'event_hour'),
      fetchResponseDistribution(activeFilters.value)
    ])

    totalDocs.value = facetResult.numFound
    facets.value = facetResult.facets
    hourlyStats.value = hourly
    responseDistribution.value = responses
    queryTime.value = Date.now() - startTime
  } catch (error) {
    console.error('Fehler beim Laden:', error)
  } finally {
    loading.value = false
  }
}

// Filter umschalten
function toggleFilter(field, value) {
  const fq = `${field}:${value}`
  const index = activeFilters.value.indexOf(fq)

  if (index === -1) {
    activeFilters.value.push(fq)
  } else {
    activeFilters.value.splice(index, 1)
  }
}

// Stunden-Filter
function addHourFilter(hour) {
  const fq = `event_hour:${hour}`
  const index = activeFilters.value.indexOf(fq)

  if (index === -1) {
    activeFilters.value.push(fq)
  } else {
    activeFilters.value.splice(index, 1)
  }
}

// Response-Time-Range-Filter
function addResponseFilter({ start, end }) {
  const fq = `response_time_ms:[${start} TO ${end}]`
  const index = activeFilters.value.indexOf(fq)

  if (index === -1) {
    activeFilters.value.push(fq)
  } else {
    activeFilters.value.splice(index, 1)
  }
}

// Alle Filter loeschen
function clearFilters() {
  activeFilters.value = []
}

// Einzelnen Filter entfernen
function removeFilter(fq) {
  const index = activeFilters.value.indexOf(fq)
  if (index !== -1) {
    activeFilters.value.splice(index, 1)
  }
}

// Neu laden wenn Filter sich aendern
watch(activeFilters, () => {
  loadData()
}, { deep: true })

// Initial laden
onMounted(() => {
  loadData()
})

// Hilfsfunktion: Zahl formatieren
function formatNumber(num) {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(0) + 'k'
  }
  return num.toLocaleString('de-DE')
}
</script>
