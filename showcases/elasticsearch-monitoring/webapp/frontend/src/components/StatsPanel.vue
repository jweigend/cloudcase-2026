<template>
  <div class="space-y-6">
    <h2 class="text-xl font-semibold text-gray-700">Statistiken</h2>
    <p class="text-sm text-gray-500 -mt-4">Klicken Sie auf Balken zum Filtern</p>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-600"></div>
    </div>

    <template v-else>
      <!-- Events pro Stunde -->
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="text-lg font-medium text-gray-700 mb-4">Events nach Stunde</h3>
        <div class="h-64 cursor-pointer">
          <Bar :data="hourlyChartData" :options="chartOptions" @click="onHourlyClick" ref="hourlyChartRef" />
        </div>
      </div>

      <!-- Response Time Verteilung -->
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="text-lg font-medium text-gray-700 mb-4">Response-Time Verteilung</h3>
        <div class="h-64 cursor-pointer">
          <Bar :data="responseChartData" :options="chartOptions" @click="onResponseClick" ref="responseChartRef" />
        </div>
      </div>

      <!-- Quick Stats -->
      <div class="grid grid-cols-3 gap-4">
        <div class="bg-white rounded-lg shadow p-4 text-center">
          <div class="text-2xl font-bold text-orange-600">
            {{ avgResponseTime }}ms
          </div>
          <div class="text-sm text-gray-500">Avg Response Time</div>
        </div>
        <div class="bg-white rounded-lg shadow p-4 text-center">
          <div class="text-2xl font-bold text-emerald-600">
            {{ peakHour }}:00
          </div>
          <div class="text-sm text-gray-500">Peak Hour</div>
        </div>
        <div class="bg-white rounded-lg shadow p-4 text-center">
          <div class="text-2xl font-bold text-purple-600">
            {{ totalEvents }}
          </div>
          <div class="text-sm text-gray-500">Gesamt Events</div>
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

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

const props = defineProps({
  hourlyStats: { type: Array, default: () => [] },
  responseDistribution: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  activeFilters: { type: Array, default: () => [] }
})

const emit = defineEmits(['add-hour-filter', 'add-response-filter'])

const hourlyChartRef = ref(null)
const responseChartRef = ref(null)

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (item) => `Events: ${formatCount(item.raw)}`
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

function onHourlyClick(event) {
  const chart = hourlyChartRef.value?.chart
  if (!chart) return

  const elements = getElementAtEvent(chart, event)
  if (elements.length === 0) return

  const index = elements[0].index
  const sortedStats = [...props.hourlyStats].sort((a, b) =>
    parseInt(a.event_hour) - parseInt(b.event_hour)
  )
  const hour = sortedStats[index]?.event_hour
  if (hour !== undefined) {
    emit('add-hour-filter', hour)
  }
}

function onResponseClick(event) {
  const chart = responseChartRef.value?.chart
  if (!chart) return

  const elements = getElementAtEvent(chart, event)
  if (elements.length === 0) return

  const index = elements[0].index
  const bucket = props.responseDistribution[index]
  if (bucket) {
    const start = bucket.val ?? (index * 200)
    const end = start + 200
    emit('add-response-filter', { start, end })
  }
}

function formatCount(count) {
  if (count >= 1000000) return (count / 1000000).toFixed(1) + 'M'
  if (count >= 1000) return (count / 1000).toFixed(0) + 'k'
  return count.toLocaleString('de-DE')
}

const hourlyChartData = computed(() => {
  const sortedStats = [...props.hourlyStats].sort((a, b) =>
    parseInt(a.event_hour) - parseInt(b.event_hour)
  )

  const backgroundColors = sortedStats.map((s) => {
    const isFiltered = props.activeFilters.includes(`event_hour:${s.event_hour}`)
    return isFiltered ? 'rgba(16, 185, 129, 1)' : 'rgba(16, 185, 129, 0.5)'
  })

  return {
    labels: sortedStats.map(s => `${String(s.event_hour).padStart(2, '0')}:00`),
    datasets: [{
      label: 'Events',
      data: sortedStats.map(s => s['count(*)']),
      backgroundColor: backgroundColors,
      borderColor: 'rgb(16, 185, 129)',
      borderWidth: 1
    }]
  }
})

const responseChartData = computed(() => {
  const backgroundColors = props.responseDistribution.map((f, index) => {
    const start = f.val ?? (index * 200)
    const end = start + 200
    const isFiltered = props.activeFilters.some(filter =>
      filter.startsWith('response_time_ms:[') && filter.includes(`${start} TO ${end}`)
    )
    return isFiltered ? 'rgba(239, 68, 68, 1)' : 'rgba(239, 68, 68, 0.5)'
  })

  return {
    labels: props.responseDistribution.map(f => f.label),
    datasets: [{
      label: 'Events',
      data: props.responseDistribution.map(f => f.count),
      backgroundColor: backgroundColors,
      borderColor: 'rgb(239, 68, 68)',
      borderWidth: 1
    }]
  }
})

const avgResponseTime = computed(() => {
  if (props.hourlyStats.length === 0) return '--'
  const totalSum = props.hourlyStats.reduce((sum, s) =>
    sum + (s['avg(response_time_ms)'] || 0) * (s['count(*)'] || 0), 0)
  const totalCount = props.hourlyStats.reduce((sum, s) => sum + (s['count(*)'] || 0), 0)
  return totalCount > 0 ? Math.round(totalSum / totalCount) : 0
})

const peakHour = computed(() => {
  if (props.hourlyStats.length === 0) return '--'
  const peak = props.hourlyStats.reduce((max, s) =>
    (s['count(*)'] || 0) > (max['count(*)'] || 0) ? s : max
  , props.hourlyStats[0])
  return String(peak.event_hour).padStart(2, '0')
})

const totalEvents = computed(() => {
  const total = props.hourlyStats.reduce((sum, s) => sum + (s['count(*)'] || 0), 0)
  if (total >= 1000000) return (total / 1000000).toFixed(1) + 'M'
  if (total >= 1000) return (total / 1000).toFixed(0) + 'k'
  return total.toLocaleString('de-DE')
})
</script>
