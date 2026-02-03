<template>
  <div class="space-y-6">
    <h2 class="text-xl font-semibold text-gray-700">📊 Statistiken</h2>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
    </div>

    <template v-else>
      <!-- Uhrzeit-Verteilung -->
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="text-lg font-medium text-gray-700 mb-4">🕐 Fahrten nach Uhrzeit</h3>
        <div class="h-64">
          <Bar :data="hourlyChartData" :options="chartOptions" />
        </div>
      </div>

      <!-- Fahrpreis-Verteilung -->
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="text-lg font-medium text-gray-700 mb-4">💵 Fahrpreis-Verteilung</h3>
        <div class="h-64">
          <Bar :data="fareChartData" :options="chartOptions" />
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
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
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
  loading: { type: Boolean, default: false }
})

// Chart Optionen
const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false }
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
  }
}

// Uhrzeit-Chart Daten
const hourlyChartData = computed(() => {
  const sortedStats = [...props.hourlyStats].sort((a, b) => 
    parseInt(a.pickup_hour) - parseInt(b.pickup_hour)
  )
  
  return {
    labels: sortedStats.map(s => `${String(s.pickup_hour).padStart(2, '0')}:00`),
    datasets: [{
      label: 'Fahrten',
      data: sortedStats.map(s => s['count(*)']),
      backgroundColor: 'rgba(59, 130, 246, 0.7)',
      borderColor: 'rgb(59, 130, 246)',
      borderWidth: 1
    }]
  }
})

// Fahrpreis-Chart Daten
const fareChartData = computed(() => ({
  labels: props.fareDistribution.map(f => f.label),
  datasets: [{
    label: 'Fahrten',
    data: props.fareDistribution.map(f => f.count),
    backgroundColor: 'rgba(34, 197, 94, 0.7)',
    borderColor: 'rgb(34, 197, 94)',
    borderWidth: 1
  }]
}))

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
