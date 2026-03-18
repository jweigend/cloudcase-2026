<template>
  <div class="bg-white rounded-lg shadow-md p-4">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-gray-800">
        Top 5 Error Sources
      </h3>
      <div class="flex items-center gap-2">
        <span
          v-if="!backendOnline"
          class="px-2 py-1 text-xs bg-red-100 text-red-700 rounded-full"
        >
          Backend offline
        </span>
        <span
          v-else-if="loading"
          class="px-2 py-1 text-xs bg-emerald-100 text-emerald-700 rounded-full animate-pulse"
        >
          Analysiere...
        </span>
        <span
          v-else-if="totalEvents > 0"
          class="px-2 py-1 text-xs bg-green-100 text-green-700 rounded-full"
        >
          {{ formatNumber(totalEvents) }} Events
        </span>
      </div>
    </div>

    <!-- Lade-Overlay -->
    <div v-if="loading" class="mb-4">
      <div class="flex items-center justify-center gap-3 py-6 bg-emerald-50 rounded-lg">
        <svg class="animate-spin h-8 w-8 text-emerald-600" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
        <div class="text-emerald-700">
          <div class="font-medium">Elasticsearch analysiert...</div>
        </div>
      </div>
    </div>

    <!-- Ergebnisse -->
    <div v-else-if="alerts.length > 0" class="space-y-3">
      <div
        v-for="(alert, index) in alerts"
        :key="`${alert.host}-${alert.service}`"
        class="p-3 rounded-lg border-l-4 transition-all hover:shadow-md"
        :class="getRankClass(index)"
      >
        <div class="flex items-start justify-between">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-lg font-bold">{{ getMedal(index) }}</span>
              <span class="font-medium text-gray-800">
                {{ alert.host }} / {{ alert.service }}
              </span>
            </div>
            <div class="text-sm text-gray-500 mt-1 truncate max-w-lg" :title="alert.latest_message">
              {{ alert.latest_message }}
            </div>
          </div>
          <div class="text-right">
            <div class="text-lg font-bold text-red-600">
              {{ alert.error_count.toLocaleString('de-DE') }}
            </div>
            <div class="text-xs text-gray-500">Errors</div>
          </div>
        </div>

        <!-- Details -->
        <div class="mt-2 grid grid-cols-3 gap-2 text-xs text-gray-600">
          <div class="bg-gray-50 rounded p-1.5 text-center">
            <div class="font-medium">{{ alert.avg_cpu }}%</div>
            <div>Avg CPU</div>
          </div>
          <div class="bg-gray-50 rounded p-1.5 text-center">
            <div class="font-medium">{{ alert.avg_memory }}%</div>
            <div>Avg Memory</div>
          </div>
          <div class="bg-gray-50 rounded p-1.5 text-center">
            <div class="font-medium">{{ alert.avg_response_ms }}ms</div>
            <div>Avg Response</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Leerer Zustand -->
    <div v-else-if="hasCalculated && alerts.length === 0" class="text-center py-8 text-gray-500">
      <div class="text-4xl mb-2">--</div>
      <div>Keine Errors fuer diese Filter</div>
    </div>

    <div v-else-if="totalEvents === 0" class="text-center py-6 text-gray-400 text-sm">
      <p>Waehle Filter aus um die</p>
      <p class="mt-1">haeufigsten Error-Quellen zu finden.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { countEvents, filtersToObject, checkBackendHealth, fetchTopAlerts } from '../api/backend.js'

const props = defineProps({
  activeFilters: {
    type: Array,
    default: () => []
  }
})

// State
const alerts = ref([])
const loading = ref(false)
const totalEvents = ref(0)
const backendOnline = ref(false)
const hasCalculated = ref(false)

let currentAbortController = null
let debounceTimer = null

async function checkBackend() {
  backendOnline.value = await checkBackendHealth()
}

async function updateCount() {
  if (!backendOnline.value) return

  try {
    const filters = filtersToObject(props.activeFilters)
    const result = await countEvents(filters)
    totalEvents.value = result.count
  } catch (error) {
    console.error('Count error:', error)
  }
}

async function calculateAlerts() {
  if (!backendOnline.value || totalEvents.value === 0) {
    alerts.value = []
    return
  }

  loading.value = true
  hasCalculated.value = true

  try {
    const filters = filtersToObject(props.activeFilters)
    const result = await fetchTopAlerts(filters, 5)
    alerts.value = result.alerts || []
    totalEvents.value = result.total_events || totalEvents.value
  } catch (error) {
    console.error('Alert calculation error:', error)
    alerts.value = []
  } finally {
    loading.value = false
  }
}

function scheduleCalculation() {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }

  alerts.value = []
  hasCalculated.value = false

  updateCount().then(() => {
    if (backendOnline.value && totalEvents.value > 0) {
      debounceTimer = setTimeout(() => {
        calculateAlerts()
      }, 300)
    }
  })
}

function getMedal(index) {
  const medals = ['1.', '2.', '3.', '4.', '5.']
  return medals[index] || `${index + 1}.`
}

function getRankClass(index) {
  const classes = [
    'border-red-400 bg-red-50',
    'border-orange-400 bg-orange-50',
    'border-yellow-400 bg-yellow-50',
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

watch(() => props.activeFilters, () => {
  scheduleCalculation()
}, { deep: true })

onUnmounted(() => {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }
})

onMounted(async () => {
  await checkBackend()
  if (backendOnline.value) {
    await updateCount()
    if (totalEvents.value > 0) {
      calculateAlerts()
    }
  }
})
</script>
