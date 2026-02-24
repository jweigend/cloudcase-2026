<template>
  <div class="space-y-6">
    <h2 class="text-xl font-semibold text-gray-700">📊 Statistiken</h2>
    <p class="text-sm text-gray-500 -mt-4">💡 Klicken Sie auf Balken zum Filtern</p>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
    </div>

    <template v-else>
      <!-- Uhrzeit-Verteilung -->
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="text-lg font-medium text-gray-700 mb-4">🕐 Fahrten nach Uhrzeit</h3>
        <div class="h-64 cursor-pointer">
          <Bar :data="hourlyChartData" :options="hourlyChartOptions" @click="onHourlyClick" ref="hourlyChartRef" />
        </div>
      </div>

      <!-- Fahrpreis-Verteilung -->
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="text-lg font-medium text-gray-700 mb-4">💵 Fahrpreis-Verteilung</h3>
        <div class="h-64 cursor-pointer">
          <Bar :data="fareChartData" :options="fareChartOptions" @click="onFareClick" ref="fareChartRef" />
        </div>
      </div>

      <!-- Quick Stats -->
      <div class="grid grid-cols-3 gap-4">
        <div class="bg-white rounded-lg shadow p-4 text-center">
          <div class="text-2xl font-bold text-green-600">
            ${{ avgFare.toFixed(2) }}
          </div>
          <div class="text-sm text-gray-500">Ø Fahrpreis</div>
        </div>
        <div class="bg-white rounded-lg shadow p-4 text-center">
          <div class="text-2xl font-bold text-blue-600">
            {{ peakHour }}:00
          </div>
          <div class="text-sm text-gray-500">Peak Hour</div>
        </div>
        <div class="bg-white rounded-lg shadow p-4 text-center">
          <div class="text-2xl font-bold text-purple-600">
            {{ totalRevenue }}
          </div>
          <div class="text-sm text-gray-500">Gesamtumsatz</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Bar, getElementAtEvent } from 'vue-chartjs'
import { 
  Chart as ChartJS, 
  CategoryScale, 
  LinearScale, 
  BarElement, 
  Title, 
  Tooltip, 
  Legend 
} from 'chart.js'

// Chart.js registrieren
ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

const props = defineProps({
  hourlyStats: { type: Array, default: () => [] },
  fareDistribution: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  activeFilters: { type: Array, default: () => [] }
})

const emit = defineEmits(['add-hour-filter', 'add-fare-filter'])

// Chart Refs für Click-Handling
const hourlyChartRef = ref(null)
const fareChartRef = ref(null)

// Base Chart Optionen
const baseChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        title: (items) => items[0]?.label || '',
        label: (item) => `Fahrten: ${formatCount(item.raw)}`
      }
    }
  },
  scales: {
    y: {
      beginAtZero: true,
      ticks: {
        callback: (value) => {
          if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M'
          if (value >= 1000) return (value / 1000).toFixed(0) + 'k'
          return value
        }
      }
    }
  },
  onHover: (event, elements) => {
    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default'
  }
}

// Hourly Chart Options (mit aktiven Filter-Markierungen)
const hourlyChartOptions = computed(() => ({
  ...baseChartOptions,
  plugins: {
    ...baseChartOptions.plugins,
    tooltip: {
      callbacks: {
        title: (items) => items[0]?.label || '',
        label: (item) => {
          const count = formatCount(item.raw)
          const isFiltered = isHourFiltered(item.dataIndex)
          return isFiltered ? `✓ ${count} (Filter aktiv)` : count
        }
      }
    }
  }
}))

// Fare Chart Options
const fareChartOptions = computed(() => ({
  ...baseChartOptions,
  plugins: {
    ...baseChartOptions.plugins,
    tooltip: {
      callbacks: {
        title: (items) => items[0]?.label || '',
        label: (item) => {
          const count = formatCount(item.raw)
          const isFiltered = isFareFiltered(item.dataIndex)
          return isFiltered ? `✓ ${count} (Filter aktiv)` : count
        }
      }
    }
  }
}))

// Prüfen ob eine Stunde gefiltert ist
function isHourFiltered(index) {
  const sortedStats = [...props.hourlyStats].sort((a, b) => 
    parseInt(a.pickup_hour) - parseInt(b.pickup_hour)
  )
  const hour = sortedStats[index]?.pickup_hour
  return props.activeFilters.includes(`pickup_hour:${hour}`)
}

// Prüfen ob ein Fahrpreis-Bereich gefiltert ist
function isFareFiltered(index) {
  const bucket = props.fareDistribution[index]
  if (!bucket) return false
  // Fare filter format: total_amount:[0 TO 10]
  const start = bucket.val ?? (index * 10)
  const end = start + 10
  return props.activeFilters.some(f => f.startsWith('total_amount:[') && f.includes(`${start} TO ${end}`))
}

// Klick auf Stunden-Chart
function onHourlyClick(event) {
  const chart = hourlyChartRef.value?.chart
  if (!chart) return
  
  const elements = getElementAtEvent(chart, event)
  if (elements.length === 0) return
  
  const index = elements[0].index
  const sortedStats = [...props.hourlyStats].sort((a, b) => 
    parseInt(a.pickup_hour) - parseInt(b.pickup_hour)
  )
  const hour = sortedStats[index]?.pickup_hour
  if (hour !== undefined) {
    emit('add-hour-filter', hour)
  }
}

// Klick auf Fahrpreis-Chart
function onFareClick(event) {
  const chart = fareChartRef.value?.chart
  if (!chart) return
  
  const elements = getElementAtEvent(chart, event)
  if (elements.length === 0) return
  
  const index = elements[0].index
  const bucket = props.fareDistribution[index]
  if (bucket) {
    const start = bucket.val ?? (index * 10)
    const end = start + 10
    emit('add-fare-filter', { start, end })
  }
}

function formatCount(count) {
  if (count >= 1000000) return (count / 1000000).toFixed(1) + 'M'
  if (count >= 1000) return (count / 1000).toFixed(0) + 'k'
  return count.toLocaleString('de-DE')
}

// Uhrzeit-Chart Daten
const hourlyChartData = computed(() => {
  const sortedStats = [...props.hourlyStats].sort((a, b) => 
    parseInt(a.pickup_hour) - parseInt(b.pickup_hour)
  )
  
  // Hintergrundfarben mit Highlight für aktive Filter
  const backgroundColors = sortedStats.map((s, index) => {
    const isFiltered = props.activeFilters.includes(`pickup_hour:${s.pickup_hour}`)
    return isFiltered ? 'rgba(59, 130, 246, 1)' : 'rgba(59, 130, 246, 0.5)'
  })
  
  const borderColors = sortedStats.map((s, index) => {
    const isFiltered = props.activeFilters.includes(`pickup_hour:${s.pickup_hour}`)
    return isFiltered ? 'rgb(30, 64, 175)' : 'rgb(59, 130, 246)'
  })
  
  const borderWidths = sortedStats.map((s, index) => {
    const isFiltered = props.activeFilters.includes(`pickup_hour:${s.pickup_hour}`)
    return isFiltered ? 3 : 1
  })
  
  return {
    labels: sortedStats.map(s => `${String(s.pickup_hour).padStart(2, '0')}:00`),
    datasets: [{
      label: 'Fahrten',
      data: sortedStats.map(s => s['count(*)']),
      backgroundColor: backgroundColors,
      borderColor: borderColors,
      borderWidth: borderWidths
    }]
  }
})

// Fahrpreis-Chart Daten
const fareChartData = computed(() => {
  // Hintergrundfarben mit Highlight für aktive Filter
  const backgroundColors = props.fareDistribution.map((f, index) => {
    const start = f.val ?? (index * 10)
    const end = start + 10
    const isFiltered = props.activeFilters.some(filter => 
      filter.startsWith('total_amount:[') && filter.includes(`${start} TO ${end}`)
    )
    return isFiltered ? 'rgba(34, 197, 94, 1)' : 'rgba(34, 197, 94, 0.5)'
  })
  
  const borderColors = props.fareDistribution.map((f, index) => {
    const start = f.val ?? (index * 10)
    const end = start + 10
    const isFiltered = props.activeFilters.some(filter => 
      filter.startsWith('total_amount:[') && filter.includes(`${start} TO ${end}`)
    )
    return isFiltered ? 'rgb(21, 128, 61)' : 'rgb(34, 197, 94)'
  })
  
  const borderWidths = props.fareDistribution.map((f, index) => {
    const start = f.val ?? (index * 10)
    const end = start + 10
    const isFiltered = props.activeFilters.some(filter => 
      filter.startsWith('total_amount:[') && filter.includes(`${start} TO ${end}`)
    )
    return isFiltered ? 3 : 1
  })
  
  return {
    labels: props.fareDistribution.map(f => f.label),
    datasets: [{
      label: 'Fahrten',
      data: props.fareDistribution.map(f => f.count),
      backgroundColor: backgroundColors,
      borderColor: borderColors,
      borderWidth: borderWidths
    }]
  }
})

// Berechnete Stats
const avgFare = computed(() => {
  if (props.hourlyStats.length === 0) return 0
  const totalSum = props.hourlyStats.reduce((sum, s) => sum + (s['sum(total_amount)'] || 0), 0)
  const totalCount = props.hourlyStats.reduce((sum, s) => sum + (s['count(*)'] || 0), 0)
  return totalCount > 0 ? totalSum / totalCount : 0
})

const peakHour = computed(() => {
  if (props.hourlyStats.length === 0) return '--'
  const peak = props.hourlyStats.reduce((max, s) => 
    (s['count(*)'] || 0) > (max['count(*)'] || 0) ? s : max
  , props.hourlyStats[0])
  return String(peak.pickup_hour).padStart(2, '0')
})

const totalRevenue = computed(() => {
  const total = props.hourlyStats.reduce((sum, s) => sum + (s['sum(total_amount)'] || 0), 0)
  if (total >= 1000000) return '$' + (total / 1000000).toFixed(1) + 'M'
  if (total >= 1000) return '$' + (total / 1000).toFixed(0) + 'k'
  return '$' + total.toFixed(0)
})
</script>
