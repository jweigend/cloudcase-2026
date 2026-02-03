<template>
  <div class="border-b border-gray-200 pb-4">
    <h3 class="text-sm font-medium text-gray-500 mb-2">{{ title }}</h3>
    <ul class="space-y-1">
      <li 
        v-for="item in items" 
        :key="item.value"
        @click="$emit('toggle', item.value)"
        class="flex items-center justify-between px-2 py-1.5 rounded cursor-pointer transition-colors"
        :class="isActive(item.value) 
          ? 'bg-blue-100 text-blue-800 font-medium' 
          : 'hover:bg-gray-100 text-gray-700'"
      >
        <span class="flex items-center gap-2">
          <span 
            class="w-4 h-4 rounded border flex items-center justify-center"
            :class="isActive(item.value) ? 'bg-blue-600 border-blue-600' : 'border-gray-300'"
          >
            <svg v-if="isActive(item.value)" class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
            </svg>
          </span>
          <span>{{ formatter ? formatter(item.value) : item.value }}</span>
        </span>
        <span class="text-xs text-gray-500 tabular-nums">
          {{ formatCount(item.count) }}
        </span>
      </li>
    </ul>
  </div>
</template>

<script setup>
const props = defineProps({
  title: { type: String, required: true },
  field: { type: String, required: true },
  items: { type: Array, default: () => [] },
  activeFilters: { type: Array, default: () => [] },
  formatter: { type: Function, default: null }
})

defineEmits(['toggle'])

function isActive(value) {
  return props.activeFilters.includes(`${props.field}:${value}`)
}

function formatCount(count) {
  if (count >= 1000000) {
    return (count / 1000000).toFixed(1) + 'M'
  }
  if (count >= 1000) {
    return (count / 1000).toFixed(0) + 'k'
  }
  return count.toLocaleString('de-DE')
}
</script>
