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
        @toggle="(v) => $emit('toggle-filter', 'pickup_hour', v)"
      />

      <!-- Day of Week -->
      <FacetGroup
        title="📅 Wochentag"
        field="pickup_dayofweek"
        :items="facets.pickup_dayofweek || []"
        :activeFilters="activeFilters"
        :formatter="formatDayOfWeek"
        @toggle="(v) => $emit('toggle-filter', 'pickup_dayofweek', v)"
      />

      <!-- Payment Type -->
      <FacetGroup
        title="💳 Zahlungsart"
        field="payment_type"
        :items="facets.payment_type || []"
        :activeFilters="activeFilters"
        :formatter="formatPaymentType"
        @toggle="(v) => $emit('toggle-filter', 'payment_type', v)"
      />

      <!-- Pickup Location (Top 10) -->
      <FacetGroup
        title="📍 Pickup Zone (Top 10)"
        field="PULocationID"
        :items="(facets.PULocationID || []).slice(0, 10)"
        :activeFilters="activeFilters"
        :formatter="formatLocation"
        @toggle="(v) => $emit('toggle-filter', 'PULocationID', v)"
      />
    </div>
  </div>
</template>

<script setup>
import FacetGroup from './FacetGroup.vue'

defineProps({
  facets: { type: Object, default: () => ({}) },
  activeFilters: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

defineEmits(['toggle-filter', 'clear-filters'])

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
