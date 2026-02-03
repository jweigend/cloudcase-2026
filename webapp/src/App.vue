<template>
  <div class="h-screen flex flex-col">
    <!-- Header -->
    <header class="bg-blue-600 text-white px-6 py-4 shadow-lg">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold">🚕 NYC Taxi Facet Explorer</h1>
          <p class="text-blue-200 text-sm">Cloudkoffer 2026 - Drill-Down Architektur Demo</p>
        </div>
        <div class="text-right">
          <div class="text-3xl font-bold">{{ formatNumber(totalDocs) }}</div>
          <div class="text-blue-200 text-sm">Fahrten</div>
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

      <!-- Right Panel: Statistiken + Top Routes -->
      <section class="flex-1 bg-gray-50 p-6 overflow-y-auto space-y-6">
        <StatsPanel 
          :hourlyStats="hourlyStats"
          :fareDistribution="fareDistribution"
          :loading="loading"
          :activeFilters="activeFilters"
          @add-hour-filter="addHourFilter"
          @add-fare-filter="addFareFilter"
        />
        
        <!-- Top Routes Panel -->
        <TopRoutesPanel 
          :activeFilters="activeFilters"
        />
      </section>
    </main>

    <!-- Footer -->
    <footer class="bg-gray-800 text-gray-400 px-6 py-2 text-sm">
      <div class="flex justify-between">
        <span>Solr: nyc-taxi-raw @ node1.cloud.local:8983</span>
        <span>Letzte Abfrage: {{ queryTime }}ms</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import FacetPanel from './components/FacetPanel.vue'
import StatsPanel from './components/StatsPanel.vue'
import TopRoutesPanel from './components/TopRoutesPanel.vue'
import { fetchFacets, fetchStats, fetchFareDistribution } from './api/solr.js'

// Facetten-Felder die wir anzeigen wollen
const FACET_FIELDS = [
  'pickup_hour',
  'pickup_dayofweek', 
  'payment_type',
  'PULocationID'
]

// State
const totalDocs = ref(0)
const facets = ref({})
const activeFilters = ref([])
const hourlyStats = ref([])
const fareDistribution = ref([])
const loading = ref(true)
const queryTime = ref(0)

// Daten laden
async function loadData() {
  loading.value = true
  const startTime = Date.now()

  try {
    // Parallel: Facetten, Stunden-Stats, Fahrpreis-Verteilung
    const [facetResult, hourly, fares] = await Promise.all([
      fetchFacets(activeFilters.value, FACET_FIELDS),
      fetchStats(activeFilters.value, 'pickup_hour'),
      fetchFareDistribution(activeFilters.value)
    ])

    totalDocs.value = facetResult.numFound
    facets.value = facetResult.facets
    hourlyStats.value = hourly
    fareDistribution.value = fares
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

// Stunden-Filter aus Chart hinzufügen/entfernen
function addHourFilter(hour) {
  const fq = `pickup_hour:${hour}`
  const index = activeFilters.value.indexOf(fq)
  
  if (index === -1) {
    activeFilters.value.push(fq)
  } else {
    activeFilters.value.splice(index, 1)
  }
}

// Fahrpreis-Range-Filter aus Chart hinzufügen/entfernen
function addFareFilter({ start, end }) {
  const fq = `total_amount:[${start} TO ${end}]`
  const index = activeFilters.value.indexOf(fq)
  
  if (index === -1) {
    activeFilters.value.push(fq)
  } else {
    activeFilters.value.splice(index, 1)
  }
}

// Alle Filter löschen
function clearFilters() {
  activeFilters.value = []
}

// Einzelnen Filter entfernen (für Range-Filter aus Charts)
function removeFilter(fq) {
  const index = activeFilters.value.indexOf(fq)
  if (index !== -1) {
    activeFilters.value.splice(index, 1)
  }
}

// Neu laden wenn Filter sich ändern
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
