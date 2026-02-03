<template>
  <div class="p-4">
    <!-- Header mit Filter-Status -->
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold text-gray-700">Facetten</h2>
      <button 
        v-if="activeFilters.length > 0"
        @click="$emit('clear-filters')"
        class="text-sm text-red-600 hover:text-red-800"
      >
        ✕ Filter löschen ({{ activeFilters.length }})
      </button>
    </div>

    <!-- Aktive Chart-Filter (Range Filter) -->
    <div v-if="rangeFilters.length > 0" class="mb-6 border-b border-gray-200 pb-4">
      <h3 class="text-sm font-medium text-gray-500 mb-2">📊 Chart-Filter</h3>
      <div class="flex flex-wrap gap-2">
        <span 
          v-for="filter in rangeFilters" 
          :key="filter.raw"
          @click="$emit('remove-filter', filter.raw)"
          class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800 cursor-pointer hover:bg-purple-200 transition-colors"
        >
          {{ filter.label }}
          <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
          </svg>
        </span>
      </div>
    </div>

    <!-- Loading Indicator -->
    <div v-if="loading" class="flex items-center justify-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>

    <!-- Facetten -->
    <div v-else class="space-y-6">
      <!-- Pickup Hour -->
      <FacetGroup
        title="🕐 Uhrzeit"
        field="pickup_hour"
        :items="facets.pickup_hour || []"
        :activeFilters="activeFilters"
        :formatter="formatHour"
        :expanded="expandedState.pickup_hour"
        @toggle="(v) => $emit('toggle-filter', 'pickup_hour', v)"
        @update:expanded="(v) => expandedState.pickup_hour = v"
      />

      <!-- Day of Week -->
      <FacetGroup
        title="📅 Wochentag"
        field="pickup_dayofweek"
        :items="facets.pickup_dayofweek || []"
        :activeFilters="activeFilters"
        :formatter="formatDayOfWeek"
        :expanded="expandedState.pickup_dayofweek"
        @toggle="(v) => $emit('toggle-filter', 'pickup_dayofweek', v)"
        @update:expanded="(v) => expandedState.pickup_dayofweek = v"
      />

      <!-- Payment Type -->
      <FacetGroup
        title="💳 Zahlungsart"
        field="payment_type"
        :items="facets.payment_type || []"
        :activeFilters="activeFilters"
        :formatter="formatPaymentType"
        :expanded="expandedState.payment_type"
        @toggle="(v) => $emit('toggle-filter', 'payment_type', v)"
        @update:expanded="(v) => expandedState.payment_type = v"
      />

      <!-- Pickup Location (Top 10) -->
      <FacetGroup
        title="📍 Pickup Zone (Top 10)"
        field="PULocationID"
        :items="(facets.PULocationID || []).slice(0, 10)"
        :activeFilters="activeFilters"
        :formatter="formatLocation"
        :expanded="expandedState.PULocationID"
        @toggle="(v) => $emit('toggle-filter', 'PULocationID', v)"
        @update:expanded="(v) => expandedState.PULocationID = v"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue'
import FacetGroup from './FacetGroup.vue'

const props = defineProps({
  facets: { type: Object, default: () => ({}) },
  activeFilters: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

defineEmits(['toggle-filter', 'clear-filters', 'remove-filter'])

// Zustand für Auf-/Zugeklappt (persistent während Komponenten-Lebenszyklus)
const expandedState = reactive({
  pickup_hour: true,
  pickup_dayofweek: true,
  payment_type: true,
  PULocationID: true
})

// Range-Filter (aus Charts) extrahieren
const rangeFilters = computed(() => {
  return props.activeFilters
    .filter(f => f.includes('[') && f.includes(' TO '))
    .map(f => {
      // Parse: total_amount:[0 TO 10]
      const match = f.match(/(\w+):\[(\d+) TO (\d+)\]/)
      if (match) {
        const [, field, start, end] = match
        if (field === 'total_amount') {
          return { raw: f, label: `💵 $${start}-$${end}` }
        }
        return { raw: f, label: `${field}: ${start}-${end}` }
      }
      return { raw: f, label: f }
    })
})

// Formatter-Funktionen
function formatHour(value) {
  return `${String(value).padStart(2, '0')}:00`
}

function formatDayOfWeek(value) {
  const days = ['', 'So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa']
  return days[value] || value
}

function formatPaymentType(value) {
  const types = {
    1: 'Kreditkarte',
    2: 'Bargeld',
    3: 'Keine Zahlung',
    4: 'Streit',
    5: 'Unbekannt',
    6: 'Storniert'
  }
  return types[value] || `Typ ${value}`
}

function formatLocation(value) {
  // NYC Taxi Zone IDs - die wichtigsten
  const zones = {
    132: 'JFK Airport',
    138: 'LaGuardia Airport',
    161: 'Midtown Center',
    162: 'Midtown East',
    163: 'Midtown North',
    164: 'Midtown South',
    186: 'Penn Station',
    230: 'Times Square',
    234: 'Union Square',
    236: 'Upper East Side N',
    237: 'Upper East Side S',
    238: 'Upper West Side N',
    239: 'Upper West Side S',
    48: 'Clinton East',
    79: 'East Village',
    107: 'Gramercy',
    113: 'Greenwich Village N',
    114: 'Greenwich Village S',
    170: 'Murray Hill'
  }
  return zones[value] || `Zone ${value}`
}
</script>
