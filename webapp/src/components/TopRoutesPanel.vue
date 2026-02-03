<template>
  <div class="bg-white rounded-lg shadow-md p-4">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-gray-800">
        🏆 Top 5 Lukrative Routen
      </h3>
      <div class="flex items-center gap-2">
        <!-- Status Badge -->
        <span 
          v-if="!backendOnline" 
          class="px-2 py-1 text-xs bg-red-100 text-red-700 rounded-full"
        >
          Backend offline
        </span>
        <span 
          v-else-if="tripCount > 1000000" 
          class="px-2 py-1 text-xs bg-yellow-100 text-yellow-700 rounded-full"
        >
          {{ formatNumber(tripCount) }} Fahrten - bitte Filter setzen
        </span>
        <span 
          v-else-if="tripCount > 0" 
          class="px-2 py-1 text-xs bg-green-100 text-green-700 rounded-full"
        >
          {{ formatNumber(tripCount) }} Fahrten
        </span>
      </div>
    </div>

    <!-- Berechnen Button -->
    <button
      @click="calculateRoutes"
      :disabled="!canAnalyze || loading"
      class="w-full py-3 px-4 rounded-lg font-medium transition-all mb-4"
      :class="buttonClass"
    >
      <span v-if="loading" class="flex items-center justify-center gap-2">
        <svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
        Spark-Job läuft...
      </span>
      <span v-else-if="!backendOnline">
        ⚠️ Backend nicht erreichbar
      </span>
      <span v-else-if="tripCount > 1000000">
        🔍 Mehr Filter nötig (max 1M)
      </span>
      <span v-else>
        🚀 Routen berechnen (Spark)
      </span>
    </button>

    <!-- Ergebnisse -->
    <div v-if="routes.length > 0" class="space-y-3">
      <div 
        v-for="(route, index) in routes" 
        :key="`${route.PULocationID}-${route.DOLocationID}`"
        class="p-3 rounded-lg border-l-4 transition-all hover:shadow-md"
        :class="getRankClass(index)"
      >
        <div class="flex items-start justify-between">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-lg font-bold">{{ getMedal(index) }}</span>
              <span class="font-medium text-gray-800">
                {{ getZoneName(route.PULocationID) }} ({{ route.PULocationID }}) → {{ getZoneName(route.DOLocationID) }} ({{ route.DOLocationID }})
              </span>
            </div>
            <div class="text-sm text-gray-500 mt-1">
              {{ route.trip_count.toLocaleString('de-DE') }} Fahrten
            </div>
          </div>
          <div class="text-right">
            <div class="text-lg font-bold text-green-600">
              ${{ route.fare_per_minute.toFixed(2) }}/min
            </div>
            <div class="text-xs text-gray-500">
              Score: {{ route.score.toLocaleString('de-DE', {maximumFractionDigits: 0}) }}
            </div>
          </div>
        </div>
        
        <!-- Details -->
        <div class="mt-2 grid grid-cols-3 gap-2 text-xs text-gray-600">
          <div class="bg-gray-50 rounded p-1.5 text-center">
            <div class="font-medium">${{ route.avg_fare.toFixed(2) }}</div>
            <div>∅ Fahrpreis</div>
          </div>
          <div class="bg-gray-50 rounded p-1.5 text-center">
            <div class="font-medium">{{ route.avg_duration_min.toFixed(0) }} min</div>
            <div>∅ Dauer</div>
          </div>
          <div class="bg-gray-50 rounded p-1.5 text-center">
            <div class="font-medium">{{ route.avg_distance.toFixed(1) }} mi</div>
            <div>∅ Distanz</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Leerer Zustand -->
    <div v-else-if="!loading && hasCalculated" class="text-center py-8 text-gray-500">
      <div class="text-4xl mb-2">🤔</div>
      <div>Keine Routen gefunden für diese Filter</div>
    </div>

    <!-- Hinweis -->
    <div v-else class="text-center py-6 text-gray-400 text-sm">
      <p>Wähle Filter aus und klicke "Routen berechnen"</p>
      <p class="mt-1">um die lukrativsten Strecken zu finden.</p>
    </div>

    <!-- Berechnung Info -->
    <div v-if="lastQuery" class="mt-4 pt-3 border-t border-gray-100">
      <details class="text-xs text-gray-400">
        <summary class="cursor-pointer hover:text-gray-600">Berechnungs-Details</summary>
        <pre class="mt-2 p-2 bg-gray-50 rounded overflow-x-auto">{{ lastQuery }}</pre>
        <p class="mt-1">Score = (Fahrten × ∅Preis) / ∅Dauer</p>
      </details>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { fetchTopRoutes, countTrips, filtersToObject, checkBackendHealth } from '../api/backend.js'

const props = defineProps({
  activeFilters: {
    type: Array,
    default: () => []
  }
})

// State
const routes = ref([])
const loading = ref(false)
const tripCount = ref(0)
const backendOnline = ref(false)
const hasCalculated = ref(false)
const lastQuery = ref('')
const zoneNames = ref({})

// Computed
const canAnalyze = computed(() => {
  return backendOnline.value && tripCount.value > 0 && tripCount.value <= 1000000
})

const buttonClass = computed(() => {
  if (loading.value) {
    return 'bg-blue-400 text-white cursor-wait'
  }
  if (!backendOnline.value) {
    return 'bg-gray-200 text-gray-500 cursor-not-allowed'
  }
  if (tripCount.value > 1000000) {
    return 'bg-yellow-100 text-yellow-700 cursor-not-allowed'
  }
  return 'bg-blue-600 text-white hover:bg-blue-700 cursor-pointer'
})

// Methoden
async function checkBackend() {
  backendOnline.value = await checkBackendHealth()
}

async function updateTripCount() {
  if (!backendOnline.value) return
  
  try {
    const filters = filtersToObject(props.activeFilters)
    const result = await countTrips(filters)
    tripCount.value = result.count
  } catch (error) {
    console.error('Count error:', error)
  }
}

async function calculateRoutes() {
  if (!canAnalyze.value) return
  
  loading.value = true
  hasCalculated.value = true
  
  try {
    const filters = filtersToObject(props.activeFilters)
    const result = await fetchTopRoutes(filters, 5)
    routes.value = result.routes || []
    lastQuery.value = result.query || ''
  } catch (error) {
    console.error('Route calculation error:', error)
    routes.value = []
  } finally {
    loading.value = false
  }
}

function getMedal(index) {
  const medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
  return medals[index] || `${index + 1}.`
}

function getRankClass(index) {
  const classes = [
    'border-yellow-400 bg-yellow-50',
    'border-gray-400 bg-gray-50',
    'border-orange-400 bg-orange-50',
    'border-blue-200 bg-blue-50',
    'border-blue-200 bg-blue-50'
  ]
  return classes[index] || 'border-gray-200'
}

function formatNumber(num) {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(0) + 'k'
  return num.toLocaleString('de-DE')
}

function getZoneName(id) {
  return zoneNames.value[id] || `Zone ${id}`
}

async function loadZoneNames() {
  try {
    const response = await fetch('/api/zone-names')
    if (response.ok) {
      zoneNames.value = await response.json()
    }
  } catch (error) {
    console.error('Failed to load zone names:', error)
  }
}

// Filter-Änderungen beobachten
watch(() => props.activeFilters, () => {
  routes.value = []
  hasCalculated.value = false
  updateTripCount()
}, { deep: true })

// Initial
onMounted(async () => {
  await checkBackend()
  if (backendOnline.value) {
    await loadZoneNames()
    await updateTripCount()
  }
})
</script>
