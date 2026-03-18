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
        Filter loeschen ({{ activeFilters.length }})
      </button>
    </div>

    <!-- Aktive Range-Filter -->
    <div v-if="rangeFilters.length > 0" class="mb-4 border-b border-gray-200 pb-3">
      <h3 class="text-sm font-medium text-gray-500 mb-2">Chart-Filter</h3>
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
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
    </div>

    <!-- Facetten -->
    <div v-else class="space-y-3">
      <FacetGroup
        title="Severity"
        field="severity"
        :items="facets.severity || []"
        :activeFilters="activeFilters"
        :formatter="formatSeverity"
        :expanded="expandedState.severity"
        @toggle="(v) => $emit('toggle-filter', 'severity', v)"
        @update:expanded="(v) => expandedState.severity = v"
      />

      <FacetGroup
        title="Event Type"
        field="event_type"
        :items="facets.event_type || []"
        :activeFilters="activeFilters"
        :expanded="expandedState.event_type"
        @toggle="(v) => $emit('toggle-filter', 'event_type', v)"
        @update:expanded="(v) => expandedState.event_type = v"
      />

      <FacetGroup
        title="Host"
        field="host"
        :items="facets.host || []"
        :activeFilters="activeFilters"
        :expanded="expandedState.host"
        @toggle="(v) => $emit('toggle-filter', 'host', v)"
        @update:expanded="(v) => expandedState.host = v"
      />

      <FacetGroup
        title="Service"
        field="service"
        :items="facets.service || []"
        :activeFilters="activeFilters"
        :expanded="expandedState.service"
        @toggle="(v) => $emit('toggle-filter', 'service', v)"
        @update:expanded="(v) => expandedState.service = v"
      />

      <FacetGroup
        title="HTTP Status"
        field="status_code"
        :items="facets.status_code || []"
        :activeFilters="activeFilters"
        :formatter="formatStatusCode"
        :expanded="expandedState.status_code"
        sortBy="value"
        @toggle="(v) => $emit('toggle-filter', 'status_code', v)"
        @update:expanded="(v) => expandedState.status_code = v"
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

const expandedState = reactive({
  severity: false,
  event_type: false,
  host: false,
  service: false,
  status_code: false
})

// Range-Filter extrahieren
const rangeFilters = computed(() => {
  return props.activeFilters
    .filter(f => f.includes('[') && f.includes(' TO '))
    .map(f => {
      const match = f.match(/(\w+):\[(\d+) TO (\d+)\]/)
      if (match) {
        const [, field, start, end] = match
        if (field === 'response_time_ms') {
          return { raw: f, label: `${start}-${end}ms` }
        }
        return { raw: f, label: `${field}: ${start}-${end}` }
      }
      return { raw: f, label: f }
    })
})

function formatSeverity(value) {
  const labels = {
    'info': 'Info',
    'warning': 'Warning',
    'error': 'Error',
    'critical': 'Critical'
  }
  return labels[value] || value
}

function formatStatusCode(value) {
  const labels = {
    200: '200 OK',
    201: '201 Created',
    301: '301 Redirect',
    400: '400 Bad Request',
    404: '404 Not Found',
    500: '500 Internal Error',
    502: '502 Bad Gateway',
    503: '503 Unavailable'
  }
  return labels[value] || `${value}`
}
</script>
